import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ProvenanceSourceItem(BaseModel):
    """
    Contributing source feature and its originating dataset version.
    """

    role: str = Field(..., description="Role of the source (e.g. CADASTRAL, DRONE, MUNICIPAL)")
    dataset_id: Optional[uuid.UUID] = Field(None, description="Originating dataset ID")
    dataset_name: str = Field(..., description="Name of the dataset")
    dataset_version: Optional[int] = Field(None, description="Dataset version number")
    dataset_format: Optional[str] = Field(None, description="Source format (e.g. GeoJSON, Shapefile)")
    feature_id: uuid.UUID = Field(..., description="Canonical feature ID")
    feature_identifier: str = Field(..., description="Human-readable feature identifier or parcel ID")
    source_feature_id: Optional[uuid.UUID] = Field(None, description="Raw source feature ID")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Source feature attributes")
    geometry_type: str = Field("Unknown", description="Geometry type (e.g. Polygon, MultiPolygon)")


class ProvenanceRelationshipItem(BaseModel):
    """
    Match relationship and machine evidence connecting source features.
    """

    match_id: uuid.UUID = Field(..., description="FeatureMatch ID")
    source_feature_id: uuid.UUID = Field(..., description="Source feature ID in match")
    candidate_feature_id: Optional[uuid.UUID] = Field(None, description="Candidate feature ID in match")
    target_feature_id: Optional[uuid.UUID] = Field(None, description="Target/candidate feature ID in match")
    machine_score: float = Field(..., description="Machine-calculated overall confidence score (0.0 to 1.0)")
    classification: str = Field(..., description="Machine match status (e.g. MATCHED, POSSIBLE_MATCH)")
    match_tier: Optional[str] = Field(None, description="Quality tier (e.g. HIGH_CONFIDENCE, MEDIUM_CONFIDENCE)")
    candidate_rank: Optional[int] = Field(None, description="Candidate rank (1 = best)")
    candidate_role: Optional[str] = Field(None, description="Role: BEST_CANDIDATE, SECONDARY_CANDIDATE, AMBIGUOUS_CANDIDATE")
    is_best_candidate: bool = Field(True, description="Whether this was ranked #1 best candidate")
    is_ambiguous: bool = Field(False, description="Whether this match had competing candidates")
    human_decision: str = Field("ACCEPTED", description="Human review decision")
    reasons: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Detailed match signals breakdown")


class ProvenanceReviewHistoryItem(BaseModel):
    """
    Individual human review decision audit entry.
    """

    id: uuid.UUID = Field(..., description="MatchReview ID")
    match_id: uuid.UUID = Field(..., description="FeatureMatch ID")
    decision: str = Field(..., description="Decision made (ACCEPTED, REJECTED, FLAGGED)")
    comment: Optional[str] = Field(None, description="Reviewer commentary")
    reviewer_id: Optional[uuid.UUID] = Field(None, description="ID of the reviewing user or session")
    created_at: datetime = Field(..., description="Timestamp of the review decision")


class ProvenanceTimelineItem(BaseModel):
    """
    Evidence-grounded chronological milestone in the lifecycle of the unified record.
    """

    event_type: str = Field(..., description="Lifecycle event type (e.g. DATA_INGESTED, MATCH_GENERATED)")
    title: str = Field(..., description="Short display title for the event")
    description: str = Field(..., description="Human-readable description of what transpired")
    timestamp: datetime = Field(..., description="Verified timestamp of the event")
    entity_type: str = Field(..., description="Entity type involved (DATASET, FEATURE, MATCH, REVIEW, RECORD, EXPORT)")
    entity_id: Optional[str] = Field(None, description="ID of the entity")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Supplementary contextual details")


class UnifiedRecordProvenanceResponse(BaseModel):
    """
    Complete provenance response for an individual UnifiedLandRecord.
    Answers: 'Where did this unified record come from and why do we trust it?'
    """

    record_id: str = Field(..., description="Human-readable record identifier (e.g. ULR-000001)")
    record_uuid: uuid.UUID = Field(..., description="UUID primary key of the unified record")
    project_id: uuid.UUID = Field(..., description="Project ID")
    status: str = Field(..., description="Status (ACTIVE, INCOMPLETE, CONFLICT)")
    canonical_geometry_source: Dict[str, Any] = Field(
        default_factory=dict,
        description="Originating source role and feature ID for canonical geometry",
    )
    area_sqm: Optional[float] = Field(None, description="Canonical metric area in square meters")
    sources: List[ProvenanceSourceItem] = Field(default_factory=list, description="All contributing source features")
    relationships: List[ProvenanceRelationshipItem] = Field(default_factory=list, description="Accepted match relationships")
    review_history: List[ProvenanceReviewHistoryItem] = Field(default_factory=list, description="Chronological review decisions")
    timeline: List[ProvenanceTimelineItem] = Field(default_factory=list, description="Chronological lifecycle timeline")
    conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="Detected attribute or area discrepancies")


class ProjectProvenanceSummaryResponse(BaseModel):
    """
    High-level provenance and audit summary for an entire project.
    """

    project_id: uuid.UUID = Field(..., description="Project ID")
    project_name: str = Field(..., description="Project Name")
    total_unified_records: int = Field(..., description="Total unified land records synthesized")
    total_sources: int = Field(..., description="Total source features contributing to unified records")
    total_accepted_matches: int = Field(..., description="Total accepted match relationships")
    total_reviews: int = Field(..., description="Total human review decisions recorded")
    datasets: List[Dict[str, Any]] = Field(default_factory=list, description="Datasets involved in harmonization")
    latest_events: List[Dict[str, Any]] = Field(default_factory=list, description="Recent audit and export events")
