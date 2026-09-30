import time
import uuid
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.dataset import Dataset
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource
from app.models.conflict import AttributeConflict
from app.models.provenance import ProvenanceEvent
from app.models.assistant import AssistantDocument
from app.schemas.assistant import (
    SemanticDocumentCategory,
    SemanticDocumentRead,
    SemanticSearchResult,
    ReindexResponse,
)
from app.services.assistant.rag.document_builder import DocumentBuilder
from app.services.assistant.rag.embedding_provider import EmbeddingProvider

logger = logging.getLogger(__name__)


class VectorStore:
    """
    PostgreSQL-backed semantic knowledge and RAG vector store for LandSync evidence.
    Manages document indexing, dense vector generation, and cosine similarity search.
    """

    def __init__(self):
        self.embedding_provider = EmbeddingProvider()

    async def index_project(self, db: AsyncSession, project_id: uuid.UUID) -> ReindexResponse:
        """
        Indexes all structured LandSync evidence for a project into assistant_documents
        with dense vector embeddings.
        """
        start_time = time.perf_counter()

        proj = await db.get(Project, project_id)
        if not proj:
            raise ValueError(f"Project with ID '{project_id}' does not exist.")

        # 1. Clear previous index for this project
        await db.execute(
            delete(AssistantDocument).where(AssistantDocument.project_id == project_id)
        )

        # 2. Gather project entities
        ds_res = await db.execute(select(Dataset).where(Dataset.project_id == project_id))
        datasets = ds_res.scalars().all()

        records_res = await db.execute(
            select(UnifiedLandRecord)
            .options(selectinload(UnifiedLandRecord.sources))
            .where(UnifiedLandRecord.project_id == project_id)
        )
        records = records_res.scalars().all()

        conflicts_res = await db.execute(
            select(AttributeConflict)
            .options(
                selectinload(AttributeConflict.resolution),
                selectinload(AttributeConflict.unified_record),
            )
            .where(AttributeConflict.project_id == project_id)
        )
        conflicts = conflicts_res.scalars().all()

        events_res = await db.execute(
            select(ProvenanceEvent)
            .where(ProvenanceEvent.project_id == project_id)
            .order_by(ProvenanceEvent.created_at.asc())
        )
        events = events_res.scalars().all()

        # 3. Build document payloads
        docs_to_create: List[Dict[str, Any]] = []

        # Project overview doc
        docs_to_create.append(
            DocumentBuilder.build_project_document(proj, datasets, len(records), len(conflicts))
        )

        # Dataset docs
        for d in datasets:
            docs_to_create.append(DocumentBuilder.build_dataset_document(d, project_id))

        # Unified record docs
        for r in records:
            docs_to_create.append(DocumentBuilder.build_unified_record_document(r))

        # Conflict docs
        for c in conflicts:
            rec_ident = c.unified_record.record_identifier if c.unified_record else None
            docs_to_create.append(DocumentBuilder.build_conflict_document(c, rec_ident))

        # Provenance docs grouped by unified record
        record_events_map: Dict[uuid.UUID, List[ProvenanceEvent]] = {}
        for ev in events:
            if ev.unified_land_record_id:
                record_events_map.setdefault(ev.unified_land_record_id, []).append(ev)

        for rec in records:
            rec_evs = record_events_map.get(rec.id, [])
            if rec_evs:
                docs_to_create.append(
                    DocumentBuilder.build_provenance_document(
                        rec.record_identifier, rec.id, project_id, rec_evs
                    )
                )

        # 4. Generate embeddings and persist
        category_counts: Dict[str, int] = {}
        documents_indexed = 0

        for doc_data in docs_to_create:
            emb = await self.embedding_provider.get_embedding(doc_data["content"])
            doc = AssistantDocument(
                project_id=project_id,
                document_category=doc_data["document_category"],
                entity_id=doc_data["entity_id"],
                title=doc_data["title"],
                content=doc_data["content"],
                doc_metadata=doc_data.get("metadata", {}),
                embedding=emb,
            )
            db.add(doc)
            documents_indexed += 1
            cat = doc_data["document_category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1

        await db.commit()

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return ReindexResponse(
            project_id=project_id,
            documents_indexed=documents_indexed,
            categories_indexed=category_counts,
            duration_ms=latency_ms,
        )

    async def semantic_search(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
    ) -> List[SemanticSearchResult]:
        """
        Executes a dense vector semantic similarity search over project evidence documents.
        """
        query_vector = await self.embedding_provider.get_embedding(query)

        stmt = select(AssistantDocument).where(AssistantDocument.project_id == project_id)
        if category:
            stmt = stmt.where(AssistantDocument.document_category == category)

        res = await db.execute(stmt)
        docs = res.scalars().all()

        if not docs:
            # If no docs are indexed yet for this project, attempt on-demand index
            try:
                await self.index_project(db, project_id)
                res = await db.execute(stmt)
                docs = res.scalars().all()
            except Exception:
                pass

        scored_results: List[SemanticSearchResult] = []
        for d in docs:
            if not d.embedding:
                continue
            # Cosine similarity (unit L2 vectors dot product)
            score = sum(a * b for a, b in zip(query_vector, d.embedding))
            # Normalize score to [0.0, 1.0]
            normalized_score = round(max(0.0, min(1.0, (score + 1.0) / 2.0)), 4)
            scored_results.append(
                SemanticSearchResult(
                    document=SemanticDocumentRead(
                        id=d.id,
                        project_id=d.project_id,
                        document_category=d.document_category,
                        entity_id=d.entity_id,
                        title=d.title,
                        content=d.content,
                        metadata=d.doc_metadata,
                        created_at=d.created_at,
                    ),
                    similarity_score=normalized_score,
                )
            )

        scored_results.sort(key=lambda x: x.similarity_score, reverse=True)
        return scored_results[:limit]
