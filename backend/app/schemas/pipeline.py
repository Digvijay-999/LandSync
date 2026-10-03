import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CandidatePairItem(BaseModel):
    id: str
    source_feature_id: str
    candidate_feature_id: str
    source_identifier: str
    candidate_identifier: str
    source_survey_number: Optional[str] = None
    candidate_survey_number: Optional[str] = None
    spatial_relationship: str  # "CONTAINMENT", "OVERLAP", "PROXIMITY"
    distance_meters: float
    overlap_sqm: float
    overlap_pct: float


class CandidateGenerationRequest(BaseModel):
    source_dataset_id: Optional[uuid.UUID] = None
    candidate_dataset_ids: Optional[List[uuid.UUID]] = None
    distance_meters: float = Field(default=50.0, ge=1.0, le=1000.0)


class CandidateGenerationResponse(BaseModel):
    stage_id: str = "candidate"
    stage_number: int = 5
    status: str = "completed"
    project_id: uuid.UUID
    source_dataset_name: str
    candidate_dataset_name: str
    total_source_features: int
    total_candidate_features: int
    candidate_pair_count: int
    features_with_candidates: int
    features_without_candidates: int
    overlap_pairs_count: int
    containment_pairs_count: int
    proximity_pairs_count: int
    candidate_pairs: List[CandidatePairItem]
    execution_time_ms: float


class FeatureMatchingRunRequest(BaseModel):
    source_dataset_id: Optional[uuid.UUID] = None
    candidate_dataset_ids: Optional[List[uuid.UUID]] = None
    distance_meters: float = Field(default=50.0, ge=1.0, le=1000.0)
    matched_threshold: float = Field(default=0.75, ge=0.1, le=1.0)
    possible_threshold: float = Field(default=0.55, ge=0.1, le=1.0)


class FeatureMatchPreviewItem(BaseModel):
    id: str
    source_identifier: str
    candidate_identifier: str
    source_survey_number: Optional[str] = None
    candidate_survey_number: Optional[str] = None
    status: str
    overall_score: float
    spatial_score: float
    area_score: float
    centroid_score: float
    geometry_score: float
    attribute_score: float
    confidence_category: str  # "HIGH", "REVIEW_REQUIRED", "UNMATCHED"


class FeatureMatchingRunResponse(BaseModel):
    stage_id: str = "matching"
    stage_number: int = 6
    status: str = "completed"
    project_id: uuid.UUID
    match_run_id: uuid.UUID
    total_source_features: int
    total_candidates: int
    matched_count: int
    high_confidence_count: int
    review_required_count: int
    unmatched_count: int
    matches_preview: List[FeatureMatchPreviewItem]
    execution_time_ms: float


class HarmonizationRunRequest(BaseModel):
    match_run_id: Optional[uuid.UUID] = None
    geometry_precedence: List[str] = Field(
        default=["CADASTRAL", "DRONE", "MUNICIPAL", "OTHER"],
        description="Priority order for authoritative geometry selection",
    )
    area_tolerance_pct: float = Field(default=5.0, ge=0.1, le=50.0)


class HarmonizedRecordPreviewItem(BaseModel):
    id: str
    source_identifier: str
    candidate_identifier: str
    source_survey_number: Optional[str] = None
    candidate_survey_number: Optional[str] = None
    authoritative_geometry_source: str
    geometry_status: str
    source_area: Optional[float] = None
    candidate_area: Optional[float] = None
    harmonized_area: float
    area_discrepancy_pct: float
    source_land_use: Optional[str] = None
    candidate_land_use: Optional[str] = None
    harmonized_land_use: Optional[str] = None
    source_mutation_status: Optional[str] = None
    candidate_mutation_status: Optional[str] = None
    harmonized_mutation_status: Optional[str] = None
    source_risk_level: Optional[str] = None
    candidate_risk_level: Optional[str] = None
    harmonized_risk_level: Optional[str] = None
    conflict_count: int
    has_conflicts: bool


class HarmonizationRunResponse(BaseModel):
    stage_id: str = "harmonization"
    stage_number: int = 7
    status: str = "completed"
    project_id: uuid.UUID
    matched_pairs_processed: int
    harmonized_records_count: int
    geometry_decisions_count: int
    attributes_reconciled_count: int
    conflicts_forwarded_count: int
    records_preview: List[HarmonizedRecordPreviewItem]
    execution_time_ms: float


class ConflictDetectionRunRequest(BaseModel):
    area_low_threshold_pct: float = Field(default=2.0, ge=0.1, le=10.0)
    area_medium_threshold_pct: float = Field(default=5.0, ge=1.0, le=25.0)
    area_high_threshold_pct: float = Field(default=15.0, ge=5.0, le=50.0)
    include_geometry_metrics: bool = Field(default=True)


class ConflictDetectionRunResponse(BaseModel):
    stage_id: str = "conflict"
    stage_number: int = 8
    status: str = "completed"
    project_id: uuid.UUID
    records_scanned: int
    conflicts_detected: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    counts_by_severity: Dict[str, int] = Field(default_factory=dict)
    counts_by_type: Dict[str, int] = Field(default_factory=dict)
    conflicts_created: int
    conflicts_updated: int
    execution_time_ms: float


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


from app.schemas.confidence import (
    ConfidenceScoringRunRequest,
    ConfidenceScoringRunResponse,
)



class PipelineStageItem(BaseModel):
    stage_number: int
    stage_id: str
    name: str
    status: str  # "completed", "ready", "running", "disabled", "failed"
    is_runnable: bool
    prerequisites_met: bool
    prerequisites_message: Optional[str] = None
    description: str
    inputs_summary: Optional[Dict[str, Any]] = None
    results_summary: Optional[Dict[str, Any]] = None
    last_run_at: Optional[datetime] = None


class PipelineStatusResponse(BaseModel):
    project_id: uuid.UUID
    project_name: str
    dataset_count: int
    total_features: int
    active_stage_number: int
    stages: List[PipelineStageItem]
