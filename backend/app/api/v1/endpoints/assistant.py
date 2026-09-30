import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.schemas.assistant import (
    AssistantQueryRequest,
    AssistantQueryResponse,
    SuggestedQuestionsResponse,
    AssistantHealthResponse,
    ReindexResponse,
    SemanticSearchResult,
)
from app.services.assistant.orchestrator import AssistantOrchestrator
from app.services.assistant.rag.vector_store import VectorStore

router = APIRouter()
_vector_store = VectorStore()


@router.post(
    "/query",
    response_model=AssistantQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query the LandSync Geospatial Evidence Assistant",
    description="Submits a natural language query with optional record/conflict context to the evidence-first LangGraph assistant.",
)
async def query_assistant(
    request: AssistantQueryRequest,
    db: AsyncSession = SessionDep,
) -> AssistantQueryResponse:
    """
    Executes LangGraph multi-step orchestration over controlled GIS and RAG tools,
    returns a verified, evidence-grounded answer with structured database entity citations.
    """
    try:
        return await AssistantOrchestrator.run_query(db, request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Assistant execution error: {str(e)}",
        )


@router.get(
    "/suggested-questions",
    response_model=SuggestedQuestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get context-aware suggested investigation questions",
    description="Returns dynamic investigation questions tailored to the active project or unified land record.",
)
async def get_suggested_questions(
    project_id: uuid.UUID = Query(..., description="Project workspace identifier"),
    context_record_id: Optional[uuid.UUID] = Query(None, description="Optional unified land record in focus"),
    db: AsyncSession = SessionDep,
) -> SuggestedQuestionsResponse:
    try:
        questions = await AssistantOrchestrator.get_suggested_questions(
            db, project_id, context_record_id
        )
        return SuggestedQuestionsResponse(
            project_id=project_id,
            context_record_id=context_record_id,
            suggested_questions=questions,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate suggested questions: {str(e)}",
        )


@router.get(
    "/health",
    response_model=AssistantHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check AI Assistant service health and capabilities",
    description="Reports model configuration, provider status, vector embedding dimension, and registered evidence tools.",
)
async def get_assistant_health() -> AssistantHealthResponse:
    settings = get_settings()
    tools = [
        "get_project_summary",
        "get_unified_record_evidence",
        "get_conflict_evidence",
        "get_provenance_trail",
        "find_records_near_coordinates",
        "find_records_in_bbox",
        "compare_feature_geometries",
        "search_unified_records_by_attributes",
        "search_source_features",
        "search_evidence_knowledge_base",
    ]
    return AssistantHealthResponse(
        status="healthy",
        ai_enabled=settings.AI_ENABLED,
        configured_provider=settings.AI_PROVIDER,
        model_name=settings.AI_MODEL_NAME,
        embedding_provider=settings.AI_EMBEDDING_PROVIDER,
        embedding_dimension=settings.AI_EMBEDDING_DIMENSION or 384,
        available_tools=tools,
    )


@router.post(
    "/projects/{project_id}/reindex",
    response_model=ReindexResponse,
    status_code=status.HTTP_200_OK,
    summary="Re-index project evidence into the vector knowledge base",
    description="Extracts structured project entities, generates dense vector embeddings, and stores them in PostgreSQL.",
)
async def reindex_project_evidence(
    project_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> ReindexResponse:
    try:
        return await _vector_store.index_project(db, project_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reindex project evidence: {str(e)}",
        )


@router.get(
    "/projects/{project_id}/semantic-search",
    response_model=List[SemanticSearchResult],
    status_code=status.HTTP_200_OK,
    summary="Perform vector semantic similarity search over project evidence",
    description="Queries the project's vector knowledge base using cosine similarity.",
)
async def semantic_search(
    project_id: uuid.UUID,
    query: str = Query(..., min_length=1, description="Semantic search query"),
    limit: int = Query(5, ge=1, le=25, description="Maximum results to return"),
    category: Optional[str] = Query(None, description="Optional document category filter"),
    db: AsyncSession = SessionDep,
) -> List[SemanticSearchResult]:
    try:
        return await _vector_store.semantic_search(
            db=db,
            project_id=project_id,
            query=query,
            limit=limit,
            category=category,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {str(e)}",
        )
