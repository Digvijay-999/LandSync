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
