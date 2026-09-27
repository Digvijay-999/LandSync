import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MatchingConfigSchema(BaseModel):
    """Configuration options for a spatial matching run."""
    candidate_search_distance_meters: float = Field(default=50.0, ge=1.0, le=5000.0)
    matched_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    possible_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    conflict_threshold: float = Field(default=0.40, ge=0.0, le=1.0)
    best_candidate_tie_tolerance: float = Field(default=0.015, ge=0.0, le=0.20)
    spatial_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    area_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    centroid_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    geometry_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    attribute_weight: float = Field(default=0.10, ge=0.0, le=1.0)
    scoring_version: str = Field(default="v1.1")


class MatchingRunCreateRequest(BaseModel):
    """Payload to start a cross-dataset feature matching run."""
    source_dataset_id: uuid.UUID
    candidate_dataset_ids: List[uuid.UUID] = Field(min_length=1)
    configuration: Optional[MatchingConfigSchema] = None


class MatchingRunRead(BaseModel):
    """Schema for a match run summary."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    source_dataset_id: uuid.UUID
    candidate_dataset_ids: List[str]
    configuration: Dict[str, Any]
    status: str
    total_features_processed: int
    total_candidates: int
    total_matches: int
    total_possible_matches: int
    total_conflicts: int
    total_unmatched: int
    quality_metrics: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime


class MatchingRunListResponse(BaseModel):
    items: List[MatchingRunRead]
    total: int


class FeatureMatchListItem(BaseModel):
    """Summarized match result for list views."""
    id: uuid.UUID
    match_run_id: uuid.UUID
    project_id: uuid.UUID
    source_feature_id: uuid.UUID
    candidate_feature_id: Optional[uuid.UUID] = None
    source_dataset_id: uuid.UUID
    candidate_dataset_id: Optional[uuid.UUID] = None
    source_identifier: str
    candidate_identifier: Optional[str] = None
    source_geometry_type: str
    candidate_geometry_type: Optional[str] = None
    source_dataset_name: str
    candidate_dataset_name: Optional[str] = None
    spatial_score: Optional[float] = None
    centroid_score: Optional[float] = None
    area_score: Optional[float] = None
    geometry_score: Optional[float] = None
    attribute_score: Optional[float] = None
    overall_score: float
    status: str
    rank: Optional[int] = None
    is_best_candidate: bool = False
    candidate_role: Optional[str] = None
    score_gap: Optional[float] = None
    candidate_count: int = 0
    review_status: str = "PENDING"
    explanation: Dict[str, Any]
    created_at: datetime


class FeatureMatchListResponse(BaseModel):
    items: List[FeatureMatchListItem]
    total: int


class SourceFeatureCandidateItem(BaseModel):
    """Individual candidate record evaluated for a given source feature."""
    match_id: uuid.UUID
    candidate_feature_id: Optional[uuid.UUID] = None
    candidate_identifier: Optional[str] = None
    candidate_dataset_id: Optional[uuid.UUID] = None
    candidate_dataset_name: Optional[str] = None
    candidate_geometry_type: Optional[str] = None
    overall_score: float
    rank: Optional[int] = None
    is_best_candidate: bool = False
    candidate_role: Optional[str] = None
    score_gap: Optional[float] = None
    review_status: str = "PENDING"
    status: str
    spatial_score: Optional[float] = None
    centroid_score: Optional[float] = None
    area_score: Optional[float] = None
    geometry_score: Optional[float] = None
    attribute_score: Optional[float] = None
    explanation: Dict[str, Any]


class SourceFeatureSummaryResponse(BaseModel):
    """Aggregated summary of all candidates for a single source feature within a run."""
    source_feature_id: uuid.UUID
    source_identifier: str
    source_dataset_id: uuid.UUID
    source_dataset_name: str
    source_geometry_type: str
    candidate_count: int
    best_candidate_id: Optional[uuid.UUID] = None
    best_candidate_identifier: Optional[str] = None
    best_score: float = 0.0
    second_best_score: Optional[float] = None
    score_gap: Optional[float] = None
    status: str
    candidate_role: Optional[str] = None
    candidates: List[SourceFeatureCandidateItem] = []


class MatchReviewCreateInput(BaseModel):
    """Payload to record an auditable human review decision."""
    decision: str = Field(..., description="Review decision: ACCEPTED, REJECTED, or FLAGGED")
    comment: Optional[str] = Field(None, max_length=2000, description="Optional reviewer comment or justification")

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        decision_upper = v.strip().upper()
        allowed = {"ACCEPTED", "REJECTED", "FLAGGED"}
        if decision_upper not in allowed:
            raise ValueError(f"Decision must be one of {allowed}, got '{v}'")
        return decision_upper


class MatchReviewResponse(BaseModel):
    """Audited review decision log."""
    id: uuid.UUID
    feature_match_id: uuid.UUID
    decision: str
    comment: Optional[str] = None
    reviewer_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class MatchDetailFeature(BaseModel):
    id: str
    source_feature_id: str
    geometry_type: str
    source_crs: str
    target_crs: str
    properties: Dict[str, Any]
    geometry: Optional[Dict[str, Any]] = None
    dataset_name: str


class MatchDetailResponse(BaseModel):
    """Complete detail of a pairwise match including full geometries, explanation, and review history."""
    id: str
    match_run_id: str
    project_id: str
    status: str
    overall_score: float
    rank: Optional[int] = None
    is_best_candidate: bool = False
    candidate_role: Optional[str] = None
    score_gap: Optional[float] = None
    candidate_count: int = 0
    review_status: str = "PENDING"
    spatial_score: Optional[float] = None
    centroid_score: Optional[float] = None
    area_score: Optional[float] = None
    geometry_score: Optional[float] = None
    attribute_score: Optional[float] = None
    explanation: Dict[str, Any]
    scoring_version: str
    created_at: datetime
    source_feature: MatchDetailFeature
    candidate_feature: Optional[MatchDetailFeature] = None
    intersection_geometry: Optional[Dict[str, Any]] = None
    reviews: List[MatchReviewResponse] = []


class ReviewQueueItem(BaseModel):
    """A prioritized candidate comparison waiting in the human review queue."""
    id: uuid.UUID
    match_run_id: uuid.UUID
    project_id: uuid.UUID
    source_feature_id: uuid.UUID
    candidate_feature_id: Optional[uuid.UUID] = None
    source_identifier: str
    candidate_identifier: Optional[str] = None
    source_dataset_name: str
    candidate_dataset_name: Optional[str] = None
    source_geometry_type: str
    candidate_geometry_type: Optional[str] = None
    overall_score: float
    status: str
    rank: Optional[int] = None
    is_best_candidate: bool = False
    candidate_role: Optional[str] = None
    score_gap: Optional[float] = None
    candidate_count: int = 0
    review_status: str = "PENDING"
    latest_comment: Optional[str] = None
    latest_decision_at: Optional[datetime] = None
    reasons: List[str] = []
    primary_reason: Optional[str] = None
    priority_category: str = "OTHER"
    priority_rank: int = 4  # 1: AMBIGUOUS, 2: CONFLICT, 3: POSSIBLE, 4: OTHER
    created_at: datetime


class ReviewQueueResponse(BaseModel):
    """Review queue list response with category badge counters."""
    total: int
    pending_count: int = 0
    ambiguous_count: int = 0
    conflict_count: int = 0
    possible_count: int = 0
    reviewed_count: int = 0
    category_counts: Optional[Dict[str, int]] = None
    items: List[ReviewQueueItem]


class ReviewStatisticsResponse(BaseModel):
    """Run-level aggregate counts of human review decisions."""
    run_id: uuid.UUID
    total_candidates: int
    pending_review: int
    accepted: int
    rejected: int
    flagged: int
    reviewed: int

