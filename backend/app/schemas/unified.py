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
    source_count: int
    geometry_source_role: Optional[str] = None
    area: Optional[float] = None
    canonical_attributes: Dict[str, Any] = {}
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
