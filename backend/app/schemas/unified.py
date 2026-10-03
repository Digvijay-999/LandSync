import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class UnifiedRecordSourceResponse(BaseModel):
    """Details of a contributing source feature in a unified land record."""

    id: uuid.UUID
    feature_id: uuid.UUID
    feature_match_id: Optional[uuid.UUID] = None
    source_role: str
    dataset_id: Optional[uuid.UUID] = None
    dataset_name: str
    source_identifier: str
    geometry_type: str
    properties: Dict[str, Any]
    geometry: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnifiedRecordListItem(BaseModel):
    """Summary item for unified land record listings."""

    id: uuid.UUID
    project_id: uuid.UUID
    record_identifier: str
    status: str
    source_count: int = 0
    geometry_source_role: Optional[str] = None
    area: Optional[float] = None
    canonical_attributes: Dict[str, Any] = {}
    harmonized_record_id: Optional[str] = None
    source_a_reference: Optional[str] = None
    source_b_reference: Optional[str] = None
    geometry_source: Optional[str] = None
    land_use: Optional[str] = None
    mutation_status: Optional[str] = None
    risk_level: Optional[str] = None
    confidence_score: Optional[float] = None
    validation_status: Optional[str] = None
    human_review_decision: Optional[str] = None
    resolution_status: str = "UNIFIED"
    metadata_trail: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnifiedRecordListResponse(BaseModel):
    """Paginated list of unified land records."""

    items: List[UnifiedRecordListItem]
    total: int
    skip: int = 0
    limit: int = 50


class UnifiedRecordDetailResponse(BaseModel):
    """Comprehensive detail representation of a unified land record."""

    id: uuid.UUID
    project_id: uuid.UUID
    record_identifier: str
    status: str
    canonical_geometry: Optional[Dict[str, Any]] = None
    geometry_source_feature_id: Optional[uuid.UUID] = None
    geometry_source_role: Optional[str] = None
    area: Optional[float] = None
    canonical_attributes: Dict[str, Any] = {}
    harmonized_record_id: Optional[str] = None
    source_a_reference: Optional[str] = None
    source_b_reference: Optional[str] = None
    geometry_source: Optional[str] = None
    land_use: Optional[str] = None
    mutation_status: Optional[str] = None
    risk_level: Optional[str] = None
    confidence_score: Optional[float] = None
    validation_status: Optional[str] = None
    human_review_decision: Optional[str] = None
    resolution_status: str = "UNIFIED"
    metadata_trail: Dict[str, Any] = {}
    sources: List[UnifiedRecordSourceResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnifiedRecordBuildResponse(BaseModel):
    """Result summary of the build/refresh operation."""

    project_id: uuid.UUID
    records_created: int
    records_updated: int
    records_unchanged: int
    accepted_relationships_processed: int
    conflict_records: int
    incomplete_records: int
    active_records: int
    total_records: int


class UnifiedRecordStatisticsResponse(BaseModel):
    """Project-level unified record metrics."""

    project_id: uuid.UUID
    total_records: int
    active: int
    incomplete: int
    conflict: int
    average_sources_per_record: float
    records_with_cadastral: int
    records_with_drone: int
    records_with_municipal: int


class Stage12ExecutionResponse(BaseModel):
    """Execution result for Pipeline Stage 12: Unified Record."""

    stage_number: int = 12
    stage_id: str = "record"
    status: str = "completed"
    project_id: uuid.UUID
    records_considered: int
    records_unified: int
    records_rejected: int
    average_confidence: float
    valid_geometries_count: int
    execution_time_ms: float
    message: str
    records_preview: List[UnifiedRecordListItem] = []


class Stage12StatusResponse(BaseModel):
    """Status summary for Pipeline Stage 12: Unified Record."""

    project_id: uuid.UUID
    stage_status: str  # ready, running, completed, disabled
    is_completed: bool
    is_runnable: bool
    records_considered: int = 0
    records_unified: int = 0
    records_rejected: int = 0
    average_confidence: float = 0.0
    valid_geometries_count: int = 0
    last_executed_at: Optional[datetime] = None

