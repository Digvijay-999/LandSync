import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.assistant import AssistantEvidenceSource, SemanticSearchResult
from app.services.assistant.rag.vector_store import VectorStore

_vector_store = VectorStore()


async def search_evidence_knowledge_base(
    db: AsyncSession,
    project_id: uuid.UUID,
    query: str,
    limit: int = 5,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes a vector semantic search over the project's indexed evidence base.
    Returns matching evidence documents and converted citations.
    """
    results: List[SemanticSearchResult] = await _vector_store.semantic_search(
        db=db,
        project_id=project_id,
        query=query,
        limit=limit,
        category=category,
    )

    evidence_items: List[AssistantEvidenceSource] = []
    for r in results:
        doc = r.document
        evidence_items.append(
            AssistantEvidenceSource(
                source_type=doc.document_category.value if hasattr(doc.document_category, "value") else str(doc.document_category),
                identifier=doc.entity_id,
                title=doc.title,
                properties=doc.metadata,
                relevance_note=f"Semantic similarity score: {r.similarity_score:.2f}. Snippet: {doc.content[:150]}...",
            )
        )

    return {
        "query": query,
        "results_count": len(results),
        "results": [
            {
                "id": str(r.document.id),
                "category": r.document.document_category.value if hasattr(r.document.document_category, "value") else str(r.document.document_category),
                "entity_id": r.document.entity_id,
                "title": r.document.title,
                "similarity_score": r.similarity_score,
                "snippet": r.document.content[:200],
            }
            for r in results
        ],
        "evidence_sources": evidence_items,
    }
