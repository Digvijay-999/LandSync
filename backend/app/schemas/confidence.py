import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


ConfidenceBucketType = Literal["HIGH", "MEDIUM", "LOW", "AMBIGUOUS"]


class ConfidenceRecordItem(BaseModel):
    """
    Detailed explainable scoring breakdown for an individual candidate parcel.
    Contains overall score, component signals, weights, contributions, and human-readable reasons.
    """
    id: str = Field(..., description="Unique identifier of the scored record or pair")
    project_id: uuid.UUID = Field(..., description="Project workspace identifier")
    record_identifier: str = Field(..., description="Display identifier for the parcel pair")
    source_identifier: str = Field(..., description="Source parcel identifier (e.g. Cadastral ref)")
    candidate_identifier: Optional[str] = Field(None, description="Candidate parcel identifier (e.g. Municipal / Drone)")
    source_feature_id: Optional[uuid.UUID] = Field(None, description="Source CanonicalFeature ID")
    candidate_feature_id: Optional[uuid.UUID] = Field(None, description="Candidate CanonicalFeature ID")
    feature_match_id: Optional[uuid.UUID] = Field(None, description="Associated FeatureMatch ID if present")
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Normalized weighted overall confidence score (0.0 to 1.0)")
    confidence_bucket: str = Field(..., description="Confidence tier: HIGH, MEDIUM, LOW, or AMBIGUOUS")
    bucket_label: str = Field(..., description="UI label: HIGH / AUTO-CONFIRM, MEDIUM / PENDING REVIEW, LOW / MANDATORY REVIEW, AMBIGUOUS / MANDATORY REVIEW")
    review_status: str = Field(..., description="Human review status: ACCEPTED, PENDING, or FLAGGED")
    spatial_score: float = Field(..., ge=0.0, le=1.0, description="Spatial IoU / proximity score")
    geometry_score: float = Field(..., ge=0.0, le=1.0, description="Geometry validity and area concordance score")
    attribute_score: float = Field(..., ge=0.0, le=1.0, description="Semantic attribute agreement score")
    temporal_score: float = Field(..., ge=0.0, le=1.0, description="Temporal alignment / survey recency score")
    weights: Dict[str, float] = Field(..., description="Component weights applied during scoring")
    contributions: Dict[str, float] = Field(..., description="Component contributions (weight * score)")
    is_ambiguous: bool = Field(default=False, description="Flag indicating multiple competing top candidates")
    has_critical_conflicts: bool = Field(default=False, description="Whether record has unresolved CRITICAL conflicts")
    critical_conflict_count: int = Field(default=0, description="Count of open critical conflicts")
    validation_status: str = Field(default="PASS", description="Stage 09 Validation status: PASS, WARNING, or FAIL")
    explanation: str = Field(..., description="Narrative explanation of the scoring determination")
    reasons: List[str] = Field(default_factory=list, description="List of explainable factor bullets")

    model_config = ConfigDict(from_attributes=True)


class ConfidenceSummaryResponse(BaseModel):
    """
    Project-level aggregate summary of confidence scoring metrics.
    """
    project_id: uuid.UUID
    total_records_scored: int = Field(..., description="Total records evaluated")
    high_count: int = Field(default=0, description="Records with HIGH confidence (>= 0.90)")
    medium_count: int = Field(default=0, description="Records with MEDIUM confidence (0.70 - 0.89)")
    low_count: int = Field(default=0, description="Records with LOW confidence (< 0.70)")
    ambiguous_count: int = Field(default=0, description="Records with ambiguous multiple competing candidates")
    review_required_count: int = Field(default=0, description="Records requiring human adjudication")
    auto_confirmed_count: int = Field(default=0, description="Records eligible for automatic confirmation")
    average_confidence: float = Field(default=0.0, description="Average overall confidence across all records")
    weights: Dict[str, float] = Field(default_factory=dict, description="Active scoring weights")
    scoring_model: str = Field(default="Multi-Component Explainable Confidence v1.0")
    execution_time_ms: Optional[float] = None
    last_run_at: Optional[datetime] = None


class ConfidenceResultListResponse(BaseModel):
    """
    Paginated list of scored records with optional summary.
    """
    items: List[ConfidenceRecordItem]
    total: int
    skip: int = 0
    limit: int = 100
    summary: Optional[ConfidenceSummaryResponse] = None


class ConfidenceScoringRunRequest(BaseModel):
    """
    Execution configuration parameters for Pipeline Stage 10.
    """
    spatial_weight: float = Field(default=0.30, ge=0.0, le=1.0, description="Weight for spatial IoU signal")
    geometry_weight: float = Field(default=0.30, ge=0.0, le=1.0, description="Weight for geometry and area concordance")
    attribute_weight: float = Field(default=0.30, ge=0.0, le=1.0, description="Weight for semantic attribute alignment")
    temporal_weight: float = Field(default=0.10, ge=0.0, le=1.0, description="Weight for temporal version/date alignment")
    high_threshold: float = Field(default=0.90, ge=0.0, le=1.0, description="Threshold for HIGH / AUTO-CONFIRM")
    medium_threshold: float = Field(default=0.70, ge=0.0, le=1.0, description="Threshold for MEDIUM / PENDING REVIEW")
    respect_critical_conflicts: bool = Field(default=True, description="Cap confidence and demand review if unresolved CRITICAL conflict or validation failed")


class ConfidenceScoringRunResponse(BaseModel):
    """
    API response returned upon successful execution of Stage 10 Confidence Scoring.
    """
    stage_id: str = "confidence"
    stage_number: int = 10
    status: str = "completed"
    project_id: uuid.UUID
    records_scored: int = 0
    total_records_scored: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    ambiguous_count: int = 0
    review_required_count: int = 0
    auto_confirmed_count: int = 0
    average_confidence: float = 0.0
    execution_time_ms: float = 0.0
    records_preview: List[ConfidenceRecordItem] = Field(default_factory=list)
