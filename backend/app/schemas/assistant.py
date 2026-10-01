import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.spatial_analysis import SpatialAnalysisResult


class AssistantIntent(str, Enum):
    """Classification of the user's geospatial/evidence query intent."""

    PROJECT_OVERVIEW = "PROJECT_OVERVIEW"
    RECORD_INVESTIGATION = "RECORD_INVESTIGATION"
    CONFLICT_EXPLANATION = "CONFLICT_EXPLANATION"
    SPATIAL_PROXIMITY = "SPATIAL_PROXIMITY"
    SPATIAL_ANALYSIS = "SPATIAL_ANALYSIS"
    COMPLEX_SPATIAL_INVESTIGATION = "COMPLEX_SPATIAL_INVESTIGATION"
    SPATIAL_CONFLICT_ANALYSIS = "SPATIAL_CONFLICT_ANALYSIS"
    DATASET_COMPARISON = "DATASET_COMPARISON"
    VERSION_COMPARISON = "VERSION_COMPARISON"
    PROVENANCE_TRACE = "PROVENANCE_TRACE"
    ATTRIBUTE_SEARCH = "ATTRIBUTE_SEARCH"
    SEMANTIC_SEARCH = "SEMANTIC_SEARCH"
    COMPLEX_INVESTIGATION = "COMPLEX_INVESTIGATION"
    GENERAL_GIS_QUERY = "GENERAL_GIS_QUERY"


class SemanticDocumentCategory(str, Enum):
    """Categories of textually represented LandSync entities for RAG embedding."""

    PROJECT = "PROJECT"
    DATASET = "DATASET"
    UNIFIED_RECORD = "UNIFIED_RECORD"
    SOURCE_FEATURE = "SOURCE_FEATURE"
    CONFLICT = "CONFLICT"
    PROVENANCE = "PROVENANCE"
    REVIEW = "REVIEW"
    AUDIT = "AUDIT"


class AssistantEvidenceSource(BaseModel):
    """
    Structured citation of a specific database entity or GIS record
    grounding an answer claim.
    """

    source_type: str = Field(
        ...,
        description="Type of entity: UNIFIED_RECORD, SOURCE_FEATURE, CANONICAL_FEATURE, FEATURE_MATCH, ATTRIBUTE_CONFLICT, PROVENANCE_EVENT, DATASET",
    )
    identifier: str = Field(
        ...,
        description="Business identifier (e.g. 'ULR-000001', 'CAD-701', 'land_use', 'MR-001')",
    )
    title: str = Field(..., description="Human-readable title for the citation")
    dataset_name: Optional[str] = Field(None, description="Originating dataset name if applicable")
    role: Optional[str] = Field(None, description="Source role: CADASTRAL, DRONE, MUNICIPAL, OTHER")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Key properties or attributes extracted")
    relevance_note: str = Field(..., description="Explanation of how this evidence substantiates the answer")

    model_config = ConfigDict(from_attributes=True)


class AssistantQueryRequest(BaseModel):
    """Request payload to query the LandSync AI Assistant."""

    query: str = Field(..., min_length=1, max_length=2000, description="Natural language question or investigation prompt")
    project_id: uuid.UUID = Field(..., description="Project workspace identifier")
    context_record_id: Optional[uuid.UUID] = Field(None, description="Optional unified land record in focus")
    context_conflict_id: Optional[uuid.UUID] = Field(None, description="Optional attribute conflict in focus")
    context_match_id: Optional[uuid.UUID] = Field(None, description="Optional feature match in focus")


class AssistantQueryResponse(BaseModel):
    """Structured response from the LandSync AI Assistant."""

    query: str
    project_id: uuid.UUID
    intent: AssistantIntent
    answer: str = Field(..., description="Comprehensive natural-language answer grounded in evidence")
    reasoning_steps: List[str] = Field(
        default_factory=list,
        description="Audit trace of tools dispatched, evidence retrieved, and verification checks",
    )
    evidence_sources: List[AssistantEvidenceSource] = Field(
        default_factory=list,
        description="Structured citations linking directly to underlying LandSync records",
    )
    suggested_followups: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up investigation questions tailored to the findings",
    )
    grounded_score: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Fraction of claims grounded in verified database evidence (1.0 = fully verified)",
    )
    execution_time_ms: float = Field(..., description="Total pipeline execution latency in milliseconds")
    spatial_result: Optional[SpatialAnalysisResult] = Field(
        None,
        description="Structured spatial analysis result with GeoJSON for interactive map rendering",
    )
    conflict_proposal: Optional[Dict[str, Any]] = Field(
        None,
        description="Advisory AI conflict-resolution proposal backed by domain authority and evidence",
    )
    spatial_plan: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured spatial query plan separating target from reference datasets",
    )


class SuggestedQuestionsResponse(BaseModel):
    """List of relevant suggested investigation questions for a project context."""

    project_id: uuid.UUID
    context_record_id: Optional[uuid.UUID] = None
    suggested_questions: List[str] = Field(..., description="Suggested questions for immediate 1-click execution")


class AssistantHealthResponse(BaseModel):
    """Health and provider status of the LandSync AI Assistant service."""

    status: str
    ai_enabled: bool
    configured_provider: str
    model_name: str
    embedding_provider: str
    embedding_dimension: int
    available_tools: List[str]


class SemanticDocumentRead(BaseModel):
    """Representation of an indexed LandSync evidence document."""

    id: uuid.UUID
    project_id: uuid.UUID
    document_category: SemanticDocumentCategory
    entity_id: str
    title: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SemanticSearchResult(BaseModel):
    """Result of a vector semantic similarity search."""

    document: SemanticDocumentRead
    similarity_score: float = Field(..., ge=0.0, le=1.0)


class ReindexResponse(BaseModel):
    """Result of re-indexing project evidence into the vector knowledge store."""

    project_id: uuid.UUID
    documents_indexed: int
    categories_indexed: Dict[str, int]
    duration_ms: float
