import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class ValidationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    harmonized_record_id: str
    source_feature_id: Optional[uuid.UUID] = None
    candidate_feature_id: Optional[uuid.UUID] = None
    source_identifier: str
    candidate_identifier: str

    overall_status: str  # "PASS", "WARNING", "FAIL"
    geometry_validity_status: str
    topology_status: str
    area_status: str
    semantic_status: str
    conflict_status: str

    failure_reasons: List[str] = Field(default_factory=list)
    warning_reasons: List[str] = Field(default_factory=list)
    geometry_metrics: Dict[str, Any] = Field(default_factory=dict)
    topology_metrics: Dict[str, Any] = Field(default_factory=dict)
    area_metrics: Dict[str, Any] = Field(default_factory=dict)
    semantic_metrics: Dict[str, Any] = Field(default_factory=dict)
    conflict_metrics: Dict[str, Any] = Field(default_factory=dict)

    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class ValidationSummaryResponse(BaseModel):
    project_id: uuid.UUID
    total_validated: int
    pass_count: int
    warning_count: int
    fail_count: int
    geometry_failures: int
    topology_failures: int
    area_failures: int
    semantic_failures: int
    conflict_failures: int
    counts_by_status: Dict[str, int] = Field(default_factory=dict)
    counts_by_category: Dict[str, int] = Field(default_factory=dict)


class ValidationResultListResponse(BaseModel):
    items: List[ValidationResultRead]
    total: int
    skip: int
    limit: int
    summary: Optional[ValidationSummaryResponse] = None


class ValidationRunRequest(BaseModel):
    area_tolerance_pct: float = Field(default=5.0, ge=0.1, le=25.0)
    area_warning_threshold_pct: float = Field(default=15.0, ge=1.0, le=50.0)
    check_topology: bool = Field(default=True)
    check_semantics: bool = Field(default=True)
    consume_conflicts: bool = Field(default=True)


class ValidationRunResponse(BaseModel):
    stage_id: str = "validation"
    stage_number: int = 9
    status: str = "completed"
    project_id: uuid.UUID
    records_validated: int
    pass_count: int
    warning_count: int
    fail_count: int
    geometry_failures_count: int
    topology_failures_count: int
    area_failures_count: int
    semantic_failures_count: int
    conflict_failures_count: int
    results_created: int
    results_updated: int
    execution_time_ms: float
