import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


AdjudicationActionType = Literal[
    "ACCEPT_SOURCE_A",
    "ACCEPT_SOURCE_B",
    "MERGE_RECONCILE",
    "REJECT_UNRESOLVED",
]


class ReviewQueueItem(BaseModel):
    """
    Unified review queue item synthesizing outputs from:
    - Stage 08 (Conflicts)
    - Stage 09 (Validation)
    - Stage 10 (Confidence scoring)
    Along with previous adjudication decisions and authoritative selections.
    """
    id: str = Field(..., description="Unique record identifier (harmonized_record_id)")
    harmonized_record_id: str = Field(..., description="Harmonized candidate pair identifier")
    project_id: uuid.UUID = Field(..., description="Project workspace identifier")
    source_identifier: str = Field(..., description="Source parcel identifier (e.g. Cadastral ref)")
    candidate_identifier: str = Field(..., description="Candidate parcel identifier (e.g. Municipal / Drone)")
    source_feature_id: Optional[uuid.UUID] = Field(None, description="Source CanonicalFeature ID")
    candidate_feature_id: Optional[uuid.UUID] = Field(None, description="Candidate CanonicalFeature ID")
    feature_match_id: Optional[uuid.UUID] = Field(None, description="Associated FeatureMatch ID")

    # Stage 10 Confidence Scoring
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Normalized overall confidence score")
    confidence_bucket: str = Field(..., description="HIGH, MEDIUM, LOW, or AMBIGUOUS")
    bucket_label: str = Field(..., description="UI label for confidence bucket")
    confidence_explanation: Optional[str] = Field(None, description="Scoring narrative")
    signal_contributions: Dict[str, float] = Field(default_factory=dict, description="Component contributions")
    reasons: List[str] = Field(default_factory=list, description="Reasoning trail bullets")

    # Stage 09 Validation Results
    validation_status: str = Field(default="PASS", description="Stage 09 overall status: PASS, WARNING, FAIL")
    validation_failure_reasons: List[str] = Field(default_factory=list, description="Validation failure messages")
    validation_warning_reasons: List[str] = Field(default_factory=list, description="Validation warning messages")

    # Stage 08 Conflict Findings
    conflict_count: int = Field(default=0, description="Total active or recorded conflicts")
    highest_conflict_severity: Optional[str] = Field(None, description="CRITICAL, HIGH, MEDIUM, LOW, or None")
    has_critical_conflicts: bool = Field(default=False, description="Whether record has unresolved CRITICAL conflicts")
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="Associated conflict details")

    # Spatial Geometry Metrics
    spatial_metrics: Dict[str, Any] = Field(default_factory=dict, description="IoU, area difference, Hausdorff, centroid distance")

    # Attributes Comparison
    source_attributes: Dict[str, Any] = Field(default_factory=dict, description="Source parcel properties")
    candidate_attributes: Dict[str, Any] = Field(default_factory=dict, description="Candidate parcel properties")
    harmonized_attributes: Dict[str, Any] = Field(default_factory=dict, description="Pre-reconciled attributes")

    # Adjudication Status & Decisions
    review_status: str = Field(default="PENDING", description="Matching review status: PENDING, ACCEPTED, REJECTED, FLAGGED")
    adjudication_status: str = Field(default="UNRESOLVED", description="UNRESOLVED, RESOLVED, REJECTED")
    adjudication_action: Optional[str] = Field(None, description="ACCEPT_SOURCE_A, ACCEPT_SOURCE_B, MERGE_RECONCILE, REJECT_UNRESOLVED")
    authoritative_geometry_source: Optional[str] = Field(None, description="SOURCE_A, SOURCE_B, or CUSTOM")
    authoritative_attributes: Dict[str, Any] = Field(default_factory=dict, description="Reconciled attribute selections")
    reviewer_name: Optional[str] = Field(None, description="Adjudicator name or role")
    notes: Optional[str] = Field(None, description="Reviewer rationale/note")
    adjudicated_at: Optional[datetime] = Field(None, description="Timestamp of adjudication")
    override_applied: bool = Field(default=False, description="Whether decision overrides open critical conflict or validation fail")
    requires_mandatory_review: bool = Field(default=True, description="Whether record requires mandatory review before stage completion")

    model_config = ConfigDict(from_attributes=True)


class ReviewQueueSummaryResponse(BaseModel):
    """
    Project-level aggregate summary of human review queue and adjudication progress.
    """
    project_id: uuid.UUID
    total_review_items: int = Field(..., description="Total items in the human review queue")
    unresolved_count: int = Field(..., description="Items pending adjudication")
    resolved_count: int = Field(..., description="Items adjudicated")
    critical_count: int = Field(default=0, description="Items with unresolved CRITICAL conflicts")
    high_conflict_count: int = Field(default=0, description="Items with HIGH severity conflicts")
    medium_conflict_count: int = Field(default=0, description="Items with MEDIUM severity conflicts")
    low_conflict_count: int = Field(default=0, description="Items with LOW severity conflicts")
    accept_source_a_count: int = Field(default=0, description="Items resolved by accepting Source A")
    accept_source_b_count: int = Field(default=0, description="Items resolved by accepting Source B")
    merged_count: int = Field(default=0, description="Items resolved via custom merge/reconcile")
    rejected_count: int = Field(default=0, description="Items rejected/marked unresolved")
    average_confidence: float = Field(default=0.0, description="Average confidence score across queue items")
    stage_status: str = Field(default="ready", description="Stage 11 pipeline status: ready, running, completed")
    is_completed: bool = Field(default=False, description="True if all mandatory review items are adjudicated")
    completion_progress_pct: float = Field(default=0.0, description="Percentage of review queue completed")
    last_adjudication_at: Optional[datetime] = None


class ReviewQueueListResponse(BaseModel):
    """
    Paginated review queue list response with active filters.
    """
    items: List[ReviewQueueItem]
    total: int
    page: int = 1
    page_size: int = 50


class AdjudicationActionRequest(BaseModel):
    """
    Adjudication action submission payload.
    Supports 4 explicit reviewer decisions:
    - ACCEPT_SOURCE_A
    - ACCEPT_SOURCE_B
    - MERGE_RECONCILE (authoritative field selections)
    - REJECT_UNRESOLVED
    """
    action: AdjudicationActionType = Field(..., description="Adjudication decision type")
    notes: Optional[str] = Field(None, description="Reviewer justification/note (required for REJECT, MERGE, or conflict override)")
    reviewer_name: Optional[str] = Field(default="Lead GIS Adjudicator", description="Name or role of reviewer")
    authoritative_geometry_source: Optional[Literal["SOURCE_A", "SOURCE_B", "CUSTOM"]] = Field(
        None, description="Selected geometry source for MERGE_RECONCILE"
    )
    authoritative_attributes: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Reconciled attribute map (e.g. land_use, mutation_status, risk_level, survey_number)",
    )


class AdjudicationActionResponse(BaseModel):
    """
    Response returned after recording an adjudication decision.
    """
    success: bool = True
    record_id: str
    action: str
    status: str
    decision: ReviewQueueItem
    summary: ReviewQueueSummaryResponse
    stage_status: str
    is_stage_completed: bool
    message: str


class Stage11ExecutionResponse(BaseModel):
    """
    Stage 11 execution / evaluation response.
    """
    stage_number: int = 11
    stage_id: str = "review"
    status: str = Field(..., description="ready, running, or completed")
    records_adjudicated: int
    records_pending: int
    summary: ReviewQueueSummaryResponse
    message: str
