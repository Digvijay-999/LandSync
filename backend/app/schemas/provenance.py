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

    id: uuid.UUID = Field(..., description="MatchReview or HumanReviewDecision ID")
    match_id: Optional[uuid.UUID] = Field(None, description="FeatureMatch ID")
    decision: str = Field(..., description="Decision made (ACCEPTED, REJECTED, FLAGGED, ACCEPT_SOURCE_A, etc.)")
    comment: Optional[str] = Field(None, description="Reviewer commentary")
    reviewer_id: Optional[str] = Field(None, description="ID or name of the reviewing user or session")
    created_at: datetime = Field(..., description="Timestamp of the review decision")


class ProvenanceTimelineItem(BaseModel):
    """
    Evidence-grounded chronological milestone in the lifecycle of the unified record.
    """

    event_type: str = Field(..., description="Lifecycle event type (e.g. RECORD_INGESTED, CANDIDATE_GENERATED, etc.)")
    title: str = Field(..., description="Short display title for the event")
    description: str = Field(..., description="Human-readable description of what transpired")
    timestamp: datetime = Field(..., description="Verified timestamp of the event")
    entity_type: str = Field(..., description="Entity type involved (DATASET, FEATURE, MATCH, HARMONIZATION, CONFLICT, VALIDATION, CONFIDENCE, REVIEW, RECORD, PROVENANCE)")
    entity_id: Optional[str] = Field(None, description="ID of the entity")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Supplementary contextual details")


class ProvenanceGraphNode(BaseModel):
    """Lineage DAG Node."""
    id: str = Field(..., description="Unique node identifier")
    type: str = Field(..., description="Node type e.g. DATASET, FEATURE, MATCH, HARMONIZATION, CONFLICT, VALIDATION, CONFIDENCE, REVIEW, UNIFIED_RECORD")
    label: str = Field(..., description="Human readable label")
    stage: int = Field(..., description="Pipeline stage number (1 to 13)")
    status: str = Field("COMPLETED", description="Status e.g. COMPLETED, ACTIVE, RESOLVED, REJECTED")
    details: Dict[str, Any] = Field(default_factory=dict, description="Node attribute metadata")


class ProvenanceGraphEdge(BaseModel):
    """Lineage DAG Edge."""
    source: str = Field(..., description="Source node id")
    target: str = Field(..., description="Target node id")
    relationship: str = Field("LEADS_TO", description="Relationship semantics")


class ProvenanceGraph(BaseModel):
    """Complete Lineage Graph."""
    nodes: List[ProvenanceGraphNode] = Field(default_factory=list)
    edges: List[ProvenanceGraphEdge] = Field(default_factory=list)


class UnifiedRecordProvenanceResponse(BaseModel):
    """
    Complete provenance response for an individual UnifiedLandRecord (backwards compatibility).
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


# =============================================================================
# STAGE 13: FIRST-CLASS PERSISTENT PROVENANCE SCHEMAS
# =============================================================================

class ProvenanceRecordItem(BaseModel):
    """
    Summary view of a persistent ProvenanceRecord for data tables and listing.
    """
    id: uuid.UUID = Field(..., description="Provenance record primary key UUID")
    project_id: uuid.UUID = Field(..., description="Project UUID")
    unified_land_record_id: uuid.UUID = Field(..., description="Associated UnifiedLandRecord UUID")
    harmonized_record_id: str = Field(..., description="Harmonized record identifier")
    record_identifier: str = Field(..., description="Unified record identifier (e.g. ULR-xxx)")

    source_dataset_ids: List[str] = Field(default_factory=list, description="Contributing dataset UUIDs")
    source_feature_ids: List[str] = Field(default_factory=list, description="Contributing canonical feature UUIDs")
    source_record_identifiers: Dict[str, Any] = Field(default_factory=dict, description="Source parcel numbers / IDs by role")

    feature_match_id: Optional[uuid.UUID] = Field(None, description="FeatureMatch UUID if applicable")
    matched_record_id: Optional[str] = Field(None, description="Matched candidate pair identifier")
    conflict_ids: List[str] = Field(default_factory=list, description="Associated conflict UUIDs")
    validation_id: Optional[uuid.UUID] = Field(None, description="ValidationResult UUID if applicable")
    human_review_decision_id: Optional[uuid.UUID] = Field(None, description="HumanReviewDecision UUID if applicable")

    confidence_score: Optional[float] = Field(None, description="Overall confidence score (0.0 to 1.0)")
    confidence_bucket: Optional[str] = Field(None, description="HIGH, MEDIUM, LOW")
    resolution_status: str = Field("UNIFIED", description="UNIFIED or REJECTED")

    lineage_completeness_pct: float = Field(100.0, description="Completeness percentage based on pipeline stages present")
    lineage_status: str = Field("COMPLETE", description="COMPLETE, PARTIAL, or QUARANTINED")
    missing_stages: List[str] = Field(default_factory=list, description="List of missing stages if partial")

    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")


class ProvenanceRecordDetailResponse(BaseModel):
    """
    Full interactive inspection payload for a single Unified Land Record's provenance.
    """
    id: uuid.UUID
    project_id: uuid.UUID
    unified_land_record_id: uuid.UUID
    harmonized_record_id: str
    record_identifier: str

    source_dataset_ids: List[str] = Field(default_factory=list)
    source_feature_ids: List[str] = Field(default_factory=list)
    source_record_identifiers: Dict[str, Any] = Field(default_factory=dict)

    feature_match_id: Optional[uuid.UUID] = None
    matched_record_id: Optional[str] = None
    conflict_ids: List[str] = Field(default_factory=list)
    validation_id: Optional[uuid.UUID] = None
    human_review_decision_id: Optional[uuid.UUID] = None

    confidence_score: Optional[float] = None
    confidence_bucket: Optional[str] = None
    resolution_status: str
    lineage_completeness_pct: float
    lineage_status: str
    missing_stages: List[str] = Field(default_factory=list)

    final_record: Dict[str, Any] = Field(default_factory=dict, description="Authoritative ULR summary attributes and geometry")
    sources: List[ProvenanceSourceItem] = Field(default_factory=list, description="Contributing source features and datasets")
    processing: Dict[str, Any] = Field(default_factory=dict, description="Stage 06-10 processing evidence")
    human_decision: Dict[str, Any] = Field(default_factory=dict, description="Stage 11 human review adjudication context")
    timeline: List[ProvenanceTimelineItem] = Field(default_factory=list, description="Chronological lifecycle event sequence")
    lineage_graph: Dict[str, Any] = Field(default_factory=dict, description="Structured DAG of nodes and edges")
    metadata_trail: Dict[str, Any] = Field(default_factory=dict, description="Full audit trail dictionary")

    created_at: datetime
    updated_at: datetime


class ProjectProvenanceSummaryResponse(BaseModel):
    """
    Enriched project-level provenance summary and query response.
    Maintains 100% backwards compatibility while providing Stage 13 queryable records.
    """

    project_id: uuid.UUID = Field(..., description="Project ID")
    project_name: str = Field(..., description="Project Name")
    total_unified_records: int = Field(..., description="Total unified land records synthesized")
    total_sources: int = Field(..., description="Total source features contributing to unified records")
    total_accepted_matches: int = Field(..., description="Total accepted match relationships")
    total_reviews: int = Field(..., description="Total human review decisions recorded")
    datasets: List[Dict[str, Any]] = Field(default_factory=list, description="Datasets involved in harmonization")
    latest_events: List[Dict[str, Any]] = Field(default_factory=list, description="Recent audit and export events")

    # Stage 13 Query & Filtering Extensions
    items: List[ProvenanceRecordItem] = Field(default_factory=list, description="Paginated provenance records")
    total: int = Field(0, description="Total matching provenance records")
    skip: int = Field(0, description="Offset")
    limit: int = Field(50, description="Page limit")
    completeness_stats: Dict[str, Any] = Field(default_factory=dict, description="Lineage completeness distributions")


class Stage13ExecutionResponse(BaseModel):
    """
    Response returned upon executing Stage 13 Provenance generation.
    """
    stage_number: int = Field(13, description="Pipeline stage number")
    stage_id: str = Field("provenance", description="Unique stage identifier")
    status: str = Field("completed", description="Execution status")
    project_id: uuid.UUID = Field(..., description="Project UUID")
    records_traced: int = Field(..., description="Number of unified land records traced")
    events_count: int = Field(..., description="Number of immutable provenance events generated/verified")
    datasets_count: int = Field(..., description="Number of contributing source datasets")
    human_decisions_traced: int = Field(..., description="Number of Stage 11 human review decisions traced")
    conflicts_traced: int = Field(..., description="Number of Stage 08 conflict records traced")
    validation_events_traced: int = Field(..., description="Number of Stage 09 validation records traced")
    lineage_completeness_pct: float = Field(..., description="Average lineage completeness percentage")
    execution_time_ms: float = Field(..., description="Execution duration in milliseconds")
    message: str = Field(..., description="Human readable summary message")
    records_preview: List[ProvenanceRecordItem] = Field(default_factory=list, description="Preview of traced records")


class Stage13StatusResponse(BaseModel):
    """
    Status of Pipeline Stage 13 for a project.
    """
    project_id: uuid.UUID = Field(..., description="Project UUID")
    stage_number: int = Field(13, description="Stage number")
    stage_id: str = Field("provenance", description="Stage identifier")
    status: str = Field(..., description="Execution status: disabled, ready, running, completed")
    is_completed: bool = Field(..., description="Whether Stage 13 is completed")
    is_runnable: bool = Field(..., description="Whether Stage 13 can be executed")
    prerequisites_met: bool = Field(..., description="Whether Stage 12 is completed")
    prerequisites_message: Optional[str] = Field(None, description="Prerequisite message if blocked")
    records_traced: int = Field(0, description="Total traced records in database")
    total_events: int = Field(0, description="Total immutable provenance events")
    average_completeness_pct: float = Field(0.0, description="Average lineage completeness percentage")
    human_decisions_traced: int = Field(0, description="Human review decisions traced")
    conflicts_traced: int = Field(0, description="Conflicts traced")
    validation_events_traced: int = Field(0, description="Validation results traced")
    last_executed_at: Optional[datetime] = Field(None, description="Timestamp of last execution")
