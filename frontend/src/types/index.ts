export interface DatabaseHealth {
  connected: boolean
  postgis_installed: boolean
  postgis_version: string | null
  error: string | null
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'down'
  app: string
  version: string
  environment: string
  timestamp: string
  database: DatabaseHealth | null
}

export interface Project {
  id: string
  name: string
  description: string | null
  target_crs: string
  status: 'draft' | 'active' | 'processing' | 'completed' | 'archived'
  created_at: string
  updated_at: string
}

export interface ProjectCreateInput {
  name: string
  description?: string
  target_crs?: string
  status?: string
}

export interface ProjectListResponse {
  items: Project[]
  total: number
}

export type PipelineStageId =
  | 'ingestion'
  | 'profiling'
  | 'crs_normalization'
  | 'schema_normalization'
  | 'candidate_generation'
  | 'feature_matching'
  | 'harmonization'
  | 'conflict_detection'
  | 'validation'
  | 'confidence_scoring'
  | 'human_review'
  | 'unified_record'
  | 'provenance'
  | 'export'

export interface PipelineStageInfo {
  id: PipelineStageId
  name: string
  description: string
  status: 'idle' | 'pending' | 'active' | 'completed' | 'failed' | 'unimplemented'
}

export interface BoundingBox {
  min_x: number
  min_y: number
  max_x: number
  max_y: number
}

export interface DatasetField {
  name: string
  data_type: string
  null_count: number
  unique_count: number
}

export interface GeneralProfile {
  filename: string
  format: string
  file_size: number
  feature_count: number
}

export interface GeometryProfile {
  geometry_type: string
  geometry_type_distribution: Record<string, number>
  geometry_count: number
  valid_geometry_count: number
  invalid_geometry_count: number
  empty_geometry_count: number
  validity_percentage: number
}

export interface SpatialProfile {
  crs: string | null
  crs_name: string | null
  is_geographic: boolean | null
  bounds: BoundingBox | null
}

export interface AttributeProfile {
  field_count: number
  fields: DatasetField[]
}

export interface DatasetProfile {
  general: GeneralProfile
  geometry: GeometryProfile
  spatial: SpatialProfile
  attributes: AttributeProfile
}

export interface DatasetVersion {
  id: string
  dataset_id: string
  version_number: number
  file_size: number
  checksum: string | null
  created_at: string
}

export interface Dataset {
  id: string
  project_id: string
  name: string
  source_filename: string
  source_format: 'geojson' | 'shapefile' | 'geopackage' | 'csv' | string
  source_type: string
  status: 'ready' | 'uploaded' | 'processing' | 'error'
  feature_count: number
  geometry_type: string
  detected_crs: string | null
  bounding_box: BoundingBox | null
  file_size: number
  created_at: string
  updated_at: string
  profile?: DatasetProfile | null
  versions?: DatasetVersion[]
}

export interface DatasetListResponse {
  items: Dataset[]
  total: number
}

export interface DatasetUploadInput {
  file: File
  name?: string
  crs?: string
}

export interface GeoJSONGeometry {
  type: string
  coordinates: any
}

export interface GeoJSONFeature {
  type: 'Feature'
  id: string
  geometry: GeoJSONGeometry | null
  properties: Record<string, any>
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection'
  features: GeoJSONFeature[]
  crs?: {
    type: string
    properties: { name: string }
  }
  total: number
}

export interface FeatureRead {
  id: string
  dataset_version_id: string
  source_feature_id: string | null
  geometry_type: string
  properties: Record<string, any>
  source_crs: string
  target_crs: string | null
  created_at: string
}

export interface FeatureListResponse {
  items: FeatureRead[]
  total: number
}

export interface ProjectLayer {
  id: string
  dataset_id: string
  name: string
  source_format: string
  geometry_type: string
  feature_count: number
  source_crs: string
  target_crs: string
  bounds: BoundingBox | null
  geojson_url: string
  color?: string
}

export interface ProjectLayersResponse {
  project_id: string
  project_name: string
  target_crs: string
  combined_bounds: BoundingBox | null
  layers: ProjectLayer[]
}

// ---------------------------------------------------------------------------
// Milestone 3: Feature Matching & Spatial Reconciliation Types
// ---------------------------------------------------------------------------

export type MatchStatus = 'matched' | 'possible_match' | 'conflict' | 'unmatched'
export type CandidateRole = 'BEST' | 'SECONDARY' | 'AMBIGUOUS' | 'CONFLICT' | 'UNMATCHED'

export interface QualityMetrics {
  total_source_features: number
  features_with_candidates: number
  features_with_no_candidates: number
  features_with_one_candidate: number
  features_with_multiple_candidates: number
  features_with_unambiguous_best: number
  features_with_ambiguous_best: number
  features_with_conflict: number
}

export interface MatchRunConfiguration {
  candidate_search_distance_meters: number
  matched_threshold: number
  possible_threshold: number
  conflict_threshold: number
  best_candidate_tie_tolerance?: number
  spatial_weight: number
  area_weight: number
  centroid_weight: number
  geometry_weight: number
  attribute_weight: number
  scoring_version: string
}

export interface MatchRun {
  id: string
  project_id: string
  source_dataset_id: string
  candidate_dataset_ids: string[]
  configuration: MatchRunConfiguration
  status: 'pending' | 'running' | 'completed' | 'failed'
  total_features_processed: number
  total_candidates: number
  total_matches: number
  total_possible_matches: number
  total_conflicts: number
  total_unmatched: number
  quality_metrics?: QualityMetrics | null
  error_message?: string | null
  started_at: string
  completed_at?: string | null
  created_at: string
}

export interface MatchRunListResponse {
  items: MatchRun[]
  total: number
}

export interface ComponentScores {
  spatial_overlap: number | null
  centroid_similarity: number | null
  area_similarity: number | null
  geometry_similarity: number | null
  attribute_similarity: number | null
}

export interface FieldAlignment {
  field_a: string
  field_b: string
  value_a: string
  value_b: string
  similarity: number
  type: string
}

export interface MatchExplanation {
  overall_score: number
  status: MatchStatus
  reasons: string[]
  component_scores: ComponentScores
  applicable_weights?: Record<string, number>
  attribute_alignments?: FieldAlignment[]
  scoring_version?: string
}

export interface FeatureMatchListItem {
  id: string
  match_run_id: string
  project_id: string
  source_feature_id: string
  candidate_feature_id?: string | null
  source_dataset_id: string
  candidate_dataset_id?: string | null
  source_identifier: string
  candidate_identifier?: string | null
  source_geometry_type: string
  candidate_geometry_type?: string | null
  source_dataset_name: string
  candidate_dataset_name?: string | null
  rank?: number | null
  is_best_candidate?: boolean
  candidate_role?: CandidateRole | null
  score_gap?: number | null
  candidate_count?: number | null
  spatial_score?: number | null
  centroid_score?: number | null
  area_score?: number | null
  geometry_score?: number | null
  attribute_score?: number | null
  overall_score: number
  status: MatchStatus
  review_status: ReviewStatus
  explanation: MatchExplanation
  created_at: string
}

export interface FeatureMatchListResponse {
  items: FeatureMatchListItem[]
  total: number
}

export interface MatchDetailFeature {
  id: string
  source_feature_id: string
  geometry_type: string
  source_crs: string
  target_crs: string
  properties: Record<string, any>
  geometry?: any | null
  dataset_name: string
}

export interface MatchDetailResponse {
  id: string
  match_run_id: string
  project_id: string
  status: MatchStatus
  review_status: ReviewStatus
  rank?: number | null
  is_best_candidate?: boolean
  candidate_role?: CandidateRole | null
  score_gap?: number | null
  candidate_count?: number | null
  overall_score: number
  spatial_score?: number | null
  centroid_score?: number | null
  area_score?: number | null
  geometry_score?: number | null
  attribute_score?: number | null
  explanation: MatchExplanation
  scoring_version: string
  created_at: string
  source_feature: MatchDetailFeature
  candidate_feature?: MatchDetailFeature | null
  intersection_geometry?: any | null
  reviews: MatchReview[]
}

export interface SourceFeatureCandidateItem {
  id: string
  match_run_id: string
  candidate_feature_id: string | null
  candidate_dataset_id: string | null
  candidate_dataset_name: string | null
  candidate_identifier: string | null
  candidate_geometry_type: string | null
  overall_score: number
  status: MatchStatus
  review_status: ReviewStatus
  rank: number | null
  is_best_candidate: boolean
  candidate_role: CandidateRole | null
  score_gap: number | null
  candidate_count: number | null
  spatial_score: number | null
  centroid_score: number | null
  area_score: number | null
  geometry_score: number | null
  attribute_score: number | null
  explanation: MatchExplanation
  created_at: string
}

export interface SourceFeatureSummaryResponse {
  source_feature_id: string
  source_identifier: string
  source_dataset_id: string
  source_dataset_name: string
  source_geometry_type: string
  candidate_count: number
  best_candidate_id?: string | null
  best_candidate_identifier?: string | null
  best_score: number
  second_best_score?: number | null
  score_gap?: number | null
  status: string
  candidate_role?: string | null
  candidates: SourceFeatureCandidateItem[]
}

export interface MatchingRunCreateInput {
  source_dataset_id: string
  candidate_dataset_ids: string[]
  configuration?: Partial<MatchRunConfiguration>
}

// ---------------------------------------------------------------------------
// Milestone 4: Human Review & Reconciliation Workspace Types
// ---------------------------------------------------------------------------

export type ReviewDecision = 'ACCEPTED' | 'REJECTED' | 'FLAGGED'
export type ReviewStatus = 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'FLAGGED'

export interface MatchReview {
  id: string
  feature_match_id: string
  decision: ReviewDecision
  comment?: string | null
  reviewer_id?: string | null
  created_at: string
  updated_at: string
}

export interface MatchReviewCreateInput {
  decision: ReviewDecision
  comment?: string | null
  reviewer_id?: string | null
}

export type ReviewQueueCategory =
  | 'all'
  | 'pending'
  | 'ambiguous'
  | 'conflict'
  | 'possible'
  | 'reviewed'
  | 'accepted'
  | 'rejected'
  | 'flagged'

export interface ReviewQueueItem {
  id: string
  match_run_id: string
  project_id: string
  source_feature_id: string
  candidate_feature_id?: string | null
  source_identifier: string
  candidate_identifier?: string | null
  source_dataset_name: string
  candidate_dataset_name?: string | null
  source_geometry_type: string
  candidate_geometry_type?: string | null
  overall_score: number
  status: MatchStatus
  candidate_role?: CandidateRole | null
  rank?: number | null
  review_status: ReviewStatus
  priority_category: 'AMBIGUOUS' | 'CONFLICT' | 'POSSIBLE' | 'OTHER'
  primary_reason?: string | null
  score_gap?: number | null
  latest_review_decision?: ReviewDecision | null
  latest_review_comment?: string | null
  latest_reviewed_at?: string | null
  created_at: string
}

export interface ReviewQueueCategoryCounts {
  all: number
  pending: number
  ambiguous: number
  conflict: number
  possible: number
  reviewed: number
  accepted: number
  rejected: number
  flagged: number
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[]
  total: number
  category_counts: ReviewQueueCategoryCounts
}

export interface ReviewStatisticsResponse {
  match_run_id: string
  total_candidates: number
  pending_review: number
  accepted: number
  rejected: number
  flagged: number
  reviewed: number
}

// ---------------------------------------------------------------------------
// Milestone 5: Unified Land Records Types
// ---------------------------------------------------------------------------

export type UnifiedRecordStatus = 'ACTIVE' | 'INCOMPLETE' | 'CONFLICT'
export type SourceRole = 'CADASTRAL' | 'DRONE' | 'MUNICIPAL' | 'OTHER'

export interface UnifiedRecordSource {
  id: string
  feature_id: string
  feature_match_id?: string | null
  source_role: SourceRole
  dataset_id?: string | null
  dataset_name: string
  source_identifier: string
  geometry_type: string
  properties: Record<string, any>
  geometry?: any | null
  created_at: string
}

export interface UnifiedRecordListItem {
  id: string
  project_id: string
  record_identifier: string
  status: UnifiedRecordStatus
  source_count: number
  geometry_source_role?: string | null
  area?: number | null
  canonical_attributes: Record<string, any>
  harmonized_record_id?: string | null
  source_a_reference?: string | null
  source_b_reference?: string | null
  geometry_source?: string | null
  land_use?: string | null
  mutation_status?: string | null
  risk_level?: string | null
  confidence_score?: number | null
  validation_status?: string | null
  human_review_decision?: string | null
  resolution_status?: string
  metadata_trail?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface UnifiedRecordListResponse {
  items: UnifiedRecordListItem[]
  total: number
  skip: number
  limit: number
}

export interface UnifiedRecordDetail {
  id: string
  project_id: string
  record_identifier: string
  status: UnifiedRecordStatus
  canonical_geometry?: any | null
  geometry_source_feature_id?: string | null
  geometry_source_role?: string | null
  area?: number | null
  canonical_attributes: Record<string, any>
  harmonized_record_id?: string | null
  source_a_reference?: string | null
  source_b_reference?: string | null
  geometry_source?: string | null
  land_use?: string | null
  mutation_status?: string | null
  risk_level?: string | null
  confidence_score?: number | null
  validation_status?: string | null
  human_review_decision?: string | null
  resolution_status?: string
  metadata_trail?: Record<string, any>
  sources: UnifiedRecordSource[]
  created_at: string
  updated_at: string
}

export interface Stage12ExecutionResponse {
  stage_number: number
  stage_id: string
  status: string
  project_id: string
  records_considered: number
  records_unified: number
  records_rejected: number
  average_confidence: number
  valid_geometries_count: number
  execution_time_ms: number
  message: string
  records_preview: UnifiedRecordListItem[]
}

export interface Stage12StatusResponse {
  project_id: string
  stage_status: string
  is_completed: boolean
  is_runnable: boolean
  records_considered: number
  records_unified: number
  records_rejected: number
  average_confidence: number
  valid_geometries_count: number
  last_executed_at?: string | null
}

export interface UnifiedRecordBuildResponse {
  project_id: string
  records_created: number
  records_updated: number
  records_unchanged: number
  accepted_relationships_processed: number
  conflict_records: number
  incomplete_records: number
  active_records: number
  total_records: number
}

export interface UnifiedRecordStatistics {
  project_id: string
  total_records: number
  active: number
  incomplete: number
  conflict: number
  average_sources_per_record: number
  records_with_cadastral: number
  records_with_drone: number
  records_with_municipal: number
}

// ============================================================================
// Milestone 6: Provenance, Audit Trails & Multi-Format Export Types
// ============================================================================

export interface ProvenanceSourceItem {
  role: string
  dataset_id?: string | null
  dataset_name: string
  dataset_version?: number | null
  dataset_format?: string | null
  feature_id: string
  feature_identifier: string
  source_feature_id?: string | null
  properties: Record<string, any>
  geometry_type: string
}

export interface ProvenanceRelationshipItem {
  match_id: string
  source_feature_id: string
  candidate_feature_id?: string | null
  target_feature_id?: string | null
  machine_score: number
  classification: string
  match_tier?: string | null
  candidate_rank?: number | null
  candidate_role?: string | null
  is_best_candidate: boolean
  is_ambiguous: boolean
  human_decision: string
  reasons?: Record<string, any>
}

export interface ProvenanceReviewHistoryItem {
  id: string
  match_id: string
  decision: string
  comment?: string | null
  reviewer_id?: string | null
  created_at: string
}

export interface ProvenanceTimelineItem {
  event_type: string
  title: string
  description: string
  timestamp: string
  entity_type: string
  entity_id?: string | null
  metadata: Record<string, any>
}

export interface UnifiedRecordProvenance {
  record_id: string
  record_uuid: string
  project_id: string
  status: UnifiedRecordStatus
  canonical_geometry_source: {
    role?: string
    feature_id?: string | null
    feature_identifier?: string | null
    dataset_name?: string | null
  }
  area_sqm?: number | null
  sources: ProvenanceSourceItem[]
  relationships: ProvenanceRelationshipItem[]
  review_history: ProvenanceReviewHistoryItem[]
  timeline: ProvenanceTimelineItem[]
  conflicts: Array<Record<string, any>>
}

export interface ProjectProvenanceSummary {
  project_id: string
  project_name: string
  total_unified_records: number
  total_sources: number
  total_accepted_matches: number
  total_reviews: number
  datasets: Array<{
    id: string
    name: string
    format: string
    feature_count: number
    versions_count: number
  }>
  latest_events: Array<{
    id: string
    event_type: string
    source_type?: string | null
    metadata: Record<string, any>
    created_at: string
  }>
}

// ============================================================================
// Stage 13: Provenance & Lineage Types
// ============================================================================

export interface ProvenanceGraphNode {
  id: string
  type: string
  label: string
  stage: number
  status: string
  details: Record<string, any>
}

export interface ProvenanceGraphEdge {
  source: string
  target: string
  relationship: string
}

export interface ProvenanceGraph {
  nodes: ProvenanceGraphNode[]
  edges: ProvenanceGraphEdge[]
}

export interface ProvenanceRecordItem {
  id: string
  project_id: string
  unified_land_record_id: string
  harmonized_record_id: string
  record_identifier: string
  source_dataset_ids: string[]
  source_feature_ids: string[]
  source_record_identifiers: Record<string, any>
  feature_match_id?: string | null
  matched_record_id?: string | null
  conflict_ids: string[]
  validation_id?: string | null
  human_review_decision_id?: string | null
  confidence_score?: number | null
  confidence_bucket?: string | null
  resolution_status: string
  lineage_completeness_pct: number
  lineage_status: 'COMPLETE' | 'PARTIAL' | 'QUARANTINED' | string
  missing_stages: string[]
  created_at: string
  updated_at: string
}

export interface ProvenanceRecordDetailResponse {
  id: string
  project_id: string
  unified_land_record_id: string
  harmonized_record_id: string
  record_identifier: string
  source_dataset_ids: string[]
  source_feature_ids: string[]
  source_record_identifiers: Record<string, any>
  feature_match_id?: string | null
  matched_record_id?: string | null
  conflict_ids: string[]
  validation_id?: string | null
  human_review_decision_id?: string | null
  confidence_score?: number | null
  confidence_bucket?: string | null
  resolution_status: string
  lineage_completeness_pct: number
  lineage_status: string
  missing_stages: string[]
  final_record: Record<string, any>
  sources: ProvenanceSourceItem[]
  processing: Record<string, any>
  human_decision: Record<string, any>
  timeline: ProvenanceTimelineItem[]
  lineage_graph: ProvenanceGraph
  metadata_trail: Record<string, any>
  created_at: string
  updated_at: string
}

export interface ProjectProvenanceSummaryResponse {
  project_id: string
  project_name: string
  total_unified_records: number
  total_sources: number
  total_accepted_matches: number
  total_reviews: number
  datasets: Array<{
    id: string
    name: string
    format: string
    feature_count: number
    versions_count: number
  }>
  latest_events: Array<{
    id: string
    event_type: string
    source_type?: string | null
    metadata: Record<string, any>
    created_at: string
  }>
  items: ProvenanceRecordItem[]
  total: number
  skip: number
  limit: number
  completeness_stats: Record<string, any>
}

export interface Stage13ExecutionResponse {
  stage_number: number
  stage_id: string
  status: string
  project_id: string
  records_traced: number
  events_count: number
  datasets_count: number
  human_decisions_traced: number
  conflicts_traced: number
  validation_events_traced: number
  lineage_completeness_pct: number
  execution_time_ms: number
  message: string
  records_preview: ProvenanceRecordItem[]
}

export interface Stage13StatusResponse {
  project_id: string
  stage_number: number
  stage_id: string
  status: 'disabled' | 'ready' | 'running' | 'completed' | string
  is_completed: boolean
  is_runnable: boolean
  prerequisites_met: boolean
  prerequisites_message?: string | null
  records_traced: number
  total_events: number
  average_completeness_pct: number
  human_decisions_traced: number
  conflicts_traced: number
  validation_events_traced: number
  last_executed_at?: string | null
}

// ---------------------------------------------------------------------------
// Milestone 14: Stage 14 Export & Deliverables Types
// ---------------------------------------------------------------------------

export interface ExportCreateRequest {
  format: 'geojson' | 'csv' | 'gpkg' | string
  include_quarantined?: boolean
}

export interface ExportJobItem {
  id: string
  project_id: string
  format: string
  status: string
  filename: string
  file_size_bytes: number
  record_count: number
  authoritative_count: number
  quarantined_count: number
  include_quarantined: boolean
  crs: string
  sha256_checksum?: string | null
  manifest_data: Record<string, any>
  download_url: string
  error_message?: string | null
  created_at: string
  completed_at?: string | null
}

export interface ExportJobListResponse {
  items: ExportJobItem[]
  total: number
}

export interface ExportManifestResponse {
  project_id: string
  project_name: string
  export_id: string
  export_timestamp: string
  export_format: string
  pipeline_version: string
  crs: string
  total_records: number
  authoritative_records: number
  quarantined_records: number
  include_quarantined: boolean
  stage12_execution_id?: string | null
  stage13_execution_id?: string | null
  data_generation_timestamp: string
  schema_version: string
  file_name: string
  file_size_bytes: number
  sha256_checksum?: string | null
}

export interface Stage14ExecutionResponse {
  execution_id: string
  stage_id: string
  stage_number: number
  status: string
  message: string
  authoritative_records_count: number
  quarantined_records_count: number
  total_records_count: number
  export_job: ExportJobItem
  executed_at: string
}

export interface Stage14StatusResponse {
  status: 'disabled' | 'ready' | 'running' | 'completed' | string
  prerequisites_met: boolean
  prerequisites_message?: string | null
  authoritative_records_count: number
  quarantined_records_count: number
  total_records_count: number
  valid_geometry_count: number
  provenance_coverage_pct: number
  project_crs: string
  available_formats: string[]
  recent_exports: ExportJobItem[]
  last_run_at?: string | null
}



// ---------------------------------------------------------------------------
// Milestone 7: Attribute Conflict Detection & Reconciliation Types
// ---------------------------------------------------------------------------

export type ConflictType = 'VALUE_MISMATCH' | 'NUMERIC_DIFFERENCE' | 'NULL_VALUE_CONFLICT'
export type ConflictSeverity = 'HIGH' | 'MEDIUM' | 'LOW'
export type ConflictStatus = 'UNRESOLVED' | 'RESOLVED' | 'DISMISSED'
export type ConflictResolutionType = 'SOURCE_SELECTION' | 'MANUAL_VALUE' | 'DISMISSED'

export interface ConflictSourceValue {
  source_role: string
  dataset_id?: string | null
  dataset_name: string
  dataset_version: number
  feature_id: string
  feature_identifier: string
  value: any
}

export interface ConflictResolution {
  id: string
  conflict_id: string
  resolution_type: ConflictResolutionType
  selected_source_feature_id?: string | null
  selected_source_role?: string | null
  resolved_value: any
  comment: string
  resolved_by?: string | null
  resolved_at: string
}

export interface AttributeConflict {
  id: string
  project_id: string
  unified_land_record_id: string
  record_identifier?: string | null
  attribute_name: string
  conflict_type: ConflictType
  severity: ConflictSeverity
  status: ConflictStatus
  detected_values: ConflictSourceValue[]
  resolution?: ConflictResolution | null
  dismissal_reason?: string | null
  created_at: string
  updated_at: string
}

export interface ConflictResolveInput {
  resolution_type: 'SOURCE_SELECTION' | 'MANUAL_VALUE'
  selected_source_feature_id?: string | null
  manual_value?: any
  comment: string
  resolved_by?: string | null
}

export interface ConflictDismissInput {
  reason: string
  resolved_by?: string | null
}

export interface ConflictListResponse {
  items: AttributeConflict[]
  total: number
  unresolved_count: number
  resolved_count: number
  dismissed_count: number
  skip: number
  limit: number
}

export interface ConflictSummary {
  project_id: string
  total_conflicts: number
  unresolved_conflicts: number
  resolved_conflicts: number
  dismissed_conflicts: number
  records_with_conflicts: number
  conflicts_by_type: Record<string, number>
  conflicts_by_attribute: Record<string, number>
}

// ============================================================================
// Milestone 8 — AI Geospatial Reasoning & Evidence Assistant Types
// ============================================================================

export type AssistantIntent =
  | 'PROJECT_OVERVIEW'
  | 'RECORD_INVESTIGATION'
  | 'CONFLICT_EXPLANATION'
  | 'SPATIAL_PROXIMITY'
  | 'SPATIAL_ANALYSIS'
  | 'COMPLEX_SPATIAL_INVESTIGATION'
  | 'SPATIAL_CONFLICT_ANALYSIS'
  | 'DATASET_COMPARISON'
  | 'PROVENANCE_TRACE'
  | 'ATTRIBUTE_SEARCH'
  | 'SEMANTIC_SEARCH'
  | 'COMPLEX_INVESTIGATION'
  | 'GENERAL_GIS_QUERY'

export interface AssistantEvidenceSource {
  source_type: string
  identifier: string
  title: string
  dataset_name?: string | null
  role?: string | null
  properties: Record<string, any>
  relevance_note: string
}

export interface AssistantQueryRequest {
  query: string
  project_id: string
  context_record_id?: string | null
  context_conflict_id?: string | null
  context_match_id?: string | null
}

export interface AssistantQueryResponse {
  query: string
  project_id: string
  intent: AssistantIntent
  answer: string
  reasoning_steps: string[]
  evidence_sources: AssistantEvidenceSource[]
  suggested_followups: string[]
  grounded_score: number
  execution_time_ms: number
  spatial_result?: SpatialAnalysisResult | null
  conflict_proposal?: ConflictResolutionProposal | null
  spatial_plan?: any | null
}

export interface SuggestedQuestionsResponse {
  project_id: string
  context_record_id?: string | null
  suggested_questions: string[]
}

export interface AssistantHealthResponse {
  status: string
  ai_enabled: boolean
  configured_provider: string
  model_name: string
  embedding_provider: string
  embedding_dimension: number
  available_tools: string[]
}

export interface SemanticDocumentRead {
  id: string
  project_id: string
  document_category: string
  entity_id: string
  title: string
  content: string
  metadata: Record<string, any>
  created_at?: string
}

export interface SemanticSearchResult {
  document: SemanticDocumentRead
  similarity_score: number
}

export interface ReindexResponse {
  project_id: string
  documents_indexed: number
  categories_indexed: Record<string, number>
  duration_ms: number
}

// ============================================================================
// Milestone 9 — Advanced Geospatial Intelligence & Spatial Analysis Types
// ============================================================================

export type SpatialAnalysisType =
  | 'PROXIMITY'
  | 'BUFFER'
  | 'INTERSECTION'
  | 'CONTAINMENT'
  | 'OVERLAP'
  | 'NEAREST'
  | 'STATISTICS'
  | 'DATASET_COMPARISON'
  | 'CONFLICT_CLUSTERS'
  | 'VERSION_COMPARISON'

export interface SpatialAnalysisResult {
  analysis_id: string
  project_id: string
  analysis_type: SpatialAnalysisType
  title: string
  description: string
  source_datasets: string[]
  input_parameters: Record<string, any>
  result_count: number
  statistics: Record<string, any>
  result_geojson: {
    type: 'FeatureCollection'
    features: any[]
  }
  execution_time_ms: number
  created_at: string
}

export interface DatasetComparisonResult {
  project_id: string
  dataset_a_id: string
  dataset_a_name: string
  dataset_b_id: string
  dataset_b_name: string
  dataset_a_count: number
  dataset_b_count: number
  intersecting_count: number
  unmatched_a_count: number
  unmatched_b_count: number
  overlap_area_sqm: number
  overlap_percentage: number
  spatial_extent_comparison: Record<string, any>
  analysis: SpatialAnalysisResult
}

export interface SpatialConflictCluster {
  cluster_id: string
  conflict_count: number
  affected_record_ids: string[]
  centroid: [number, number]
  bounding_box: [number, number, number, number]
  dominant_fields: string[]
  dataset_pairs: string[]
}

export interface SpatialConflictAnalysisResult {
  project_id: string
  total_conflicts: number
  cluster_count: number
  clusters: SpatialConflictCluster[]
  dataset_pair_disagreements: Record<string, number>
  high_conflict_areas: Array<{
    cluster_id: string
    conflict_count: number
    centroid: [number, number]
    affected_records: string[]
  }>
  analysis: SpatialAnalysisResult
}

export interface ProximityAnalysisParams {
  project_id: string
  target_dataset_id?: string
  reference_dataset_id?: string
  reference_feature_id?: string
  latitude?: number
  longitude?: number
  distance_meters: number
  limit?: number
}

export interface BufferAnalysisParams {
  project_id: string
  feature_id?: string
  latitude?: number
  longitude?: number
  distance_meters: number
  target_dataset_id?: string
}

export interface IntersectionAnalysisParams {
  project_id: string
  dataset_a_id: string
  dataset_b_id: string
  min_overlap_pct?: number
  limit?: number
}

export interface ContainmentAnalysisParams {
  project_id: string
  container_dataset_id: string
  contained_dataset_id: string
  limit?: number
}

export interface DatasetComparisonParams {
  project_id: string
  dataset_a_id: string
  dataset_b_id: string
}

export interface SpatialConflictAnalysisParams {
  project_id: string
  limit?: number
}

export interface VersionComparisonParams {
  project_id: string
  dataset_id: string
  version_a_number?: number
  version_b_number?: number
}

export interface VersionDifferenceItem {
  feature_id: string
  identifier: string
  change_type: 'ADDED' | 'REMOVED' | 'CHANGED' | 'UNCHANGED'
  geometry_change?: boolean
  attribute_change?: boolean
  area_delta_sqm?: number | null
  centroid_shift_meters?: number | null
  attribute_diffs?: Record<string, any>
  properties?: Record<string, any>
}

export interface VersionComparisonResult {
  project_id: string
  dataset_id: string
  dataset_name: string
  version_a_number: number
  version_b_number: number
  status: 'success' | 'insufficient_versions'
  message?: string | null
  added_count: number
  removed_count: number
  changed_count: number
  unchanged_count: number
  changes: VersionDifferenceItem[]
  analysis?: SpatialAnalysisResult | null
}

export interface AnalysisHistorySummary {
  analysis_id: string
  project_id: string
  analysis_type: SpatialAnalysisType
  title: string
  description: string
  result_count: number
  execution_time_ms: number
  created_at: string
  status: string
}

export interface ConflictSourceReference {
  source_name: string
  feature_id?: string | null
  value?: any
  source_type?: string | null
  authority_weight?: number | null
}

export interface ConflictResolutionProposal {
  proposal_id: string
  conflict_id: string
  project_id: string
  unified_land_record_id: string
  record_identifier: string
  attribute_name: string
  conflicting_values: any[]
  recommended_value: any
  recommended_source: string
  confidence: number
  fact_statement: string
  inference_statement: string
  recommendation_statement: string
  reasoning: string
  supporting_evidence: string[]
  source_references: ConflictSourceReference[]
  requires_human_approval: boolean
  is_advisory_only: boolean
  disclaimer: string
  created_at: string
}

// ==========================================
// PIPELINE WORKFLOW & STAGE EXECUTION TYPES
// ==========================================

export interface PipelineStageItem {
  stage_number: number
  stage_id: string
  name: string
  status: 'completed' | 'ready' | 'running' | 'disabled' | 'failed'
  is_runnable: boolean
  prerequisites_met: boolean
  prerequisites_message?: string | null
  description: string
  inputs_summary?: Record<string, any> | null
  results_summary?: Record<string, any> | null
  last_run_at?: string | null
}

export interface PipelineStatusResponse {
  project_id: string
  project_name: string
  dataset_count: number
  total_features: number
  active_stage_number: number
  stages: PipelineStageItem[]
}

export interface CandidatePairItem {
  id: string
  source_feature_id: string
  candidate_feature_id: string
  source_identifier: string
  candidate_identifier: string
  source_survey_number?: string | null
  candidate_survey_number?: string | null
  spatial_relationship: 'CONTAINMENT' | 'OVERLAP' | 'PROXIMITY'
  distance_meters: number
  overlap_sqm: number
  overlap_pct: number
}

export interface CandidateGenerationRequest {
  source_dataset_id?: string | null
  candidate_dataset_ids?: string[] | null
  distance_meters?: number
}

export interface CandidateGenerationResponse {
  stage_id: string
  stage_number: number
  status: string
  project_id: string
  source_dataset_name: string
  candidate_dataset_name: string
  total_source_features: number
  total_candidate_features: number
  candidate_pair_count: number
  features_with_candidates: number
  features_without_candidates: number
  overlap_pairs_count: number
  containment_pairs_count: number
  proximity_pairs_count: number
  candidate_pairs: CandidatePairItem[]
  execution_time_ms: number
}

export interface FeatureMatchingRunRequest {
  source_dataset_id?: string | null
  candidate_dataset_ids?: string[] | null
  distance_meters?: number
  matched_threshold?: number
  possible_threshold?: number
}

export interface FeatureMatchPreviewItem {
  id: string
  source_identifier: string
  candidate_identifier: string
  source_survey_number?: string | null
  candidate_survey_number?: string | null
  status: string
  overall_score: number
  spatial_score: number
  area_score: number
  centroid_score: number
  geometry_score: number
  attribute_score: number
  confidence_category: 'HIGH' | 'REVIEW_REQUIRED' | 'UNMATCHED'
}

export interface FeatureMatchingRunResponse {
  stage_id: string
  stage_number: number
  status: string
  project_id: string
  match_run_id: string
  total_source_features: number
  total_candidates: number
  matched_count: number
  high_confidence_count: number
  review_required_count: number
  unmatched_count: number
  matches_preview: FeatureMatchPreviewItem[]
  execution_time_ms: number
}

export interface HarmonizationRunRequest {
  match_run_id?: string | null
  geometry_precedence?: string[]
  area_tolerance_pct?: number
}

export interface HarmonizedRecordPreviewItem {
  id: string
  source_identifier: string
  candidate_identifier: string
  source_survey_number?: string | null
  candidate_survey_number?: string | null
  authoritative_geometry_source: string
  geometry_status: string
  source_area?: number | null
  candidate_area?: number | null
  harmonized_area: number
  area_discrepancy_pct: number
  source_land_use?: string | null
  candidate_land_use?: string | null
  harmonized_land_use?: string | null
  source_mutation_status?: string | null
  candidate_mutation_status?: string | null
  harmonized_mutation_status?: string | null
  source_risk_level?: string | null
  candidate_risk_level?: string | null
  harmonized_risk_level?: string | null
  conflict_count: number
  has_conflicts: boolean
}

export interface HarmonizationRunResponse {
  stage_id: string
  stage_number: number
  status: string
  project_id: string
  matched_pairs_processed: number
  harmonized_records_count: number
  geometry_decisions_count: number
  attributes_reconciled_count: number
  conflicts_forwarded_count: number
  records_preview: HarmonizedRecordPreviewItem[]
  execution_time_ms: number
}

export interface GeospatialConflict {
  id: string
  project_id: string
  harmonized_record_id: string
  source_feature_id?: string | null
  candidate_feature_id?: string | null
  conflict_type: string
  category: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  severity_reason?: string | null
  status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED' | 'DISMISSED'
  source_a: string
  source_b: string
  field_name: string
  value_a?: string | null
  value_b?: string | null
  normalized_value_a?: string | null
  normalized_value_b?: string | null
  discrepancy_value?: string | null
  discrepancy_percentage?: number | null
  detection_rule: string
  explanation?: string | null
  evidence: Record<string, any>
  geometry_metadata?: Record<string, any> | null
  idempotency_key: string
  created_at: string
  updated_at: string
}

export interface GeospatialConflictListResponse {
  items: GeospatialConflict[]
  total: number
  skip: number
  limit: number
  counts_by_severity: Record<string, number>
  counts_by_type: Record<string, number>
  counts_by_status: Record<string, number>
}

export interface ConflictDetectionRunRequest {
  area_low_threshold_pct?: number
  area_medium_threshold_pct?: number
  area_high_threshold_pct?: number
  include_geometry_metrics?: boolean
}

export interface ConflictDetectionRunResponse {
  stage_id: string
  stage_number: number
  status: string
  project_id: string
  records_scanned: number
  conflicts_detected: number
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  counts_by_severity: Record<string, number>
  counts_by_type: Record<string, number>
  conflicts_created: number
  conflicts_updated: number
  execution_time_ms: number
}

// ---------------------------------------------------------------------------
// Milestone 9: Stage 09 Validation Types
// ---------------------------------------------------------------------------

export type ValidationStatus = 'PASS' | 'WARNING' | 'FAIL'

export interface ValidationResult {
  id: string
  project_id: string
  harmonized_record_id: string
  source_feature_id?: string | null
  candidate_feature_id?: string | null
  source_identifier: string
  candidate_identifier: string
  overall_status: ValidationStatus
  geometry_validity_status: ValidationStatus
  topology_status: ValidationStatus
  area_status: ValidationStatus
  semantic_status: ValidationStatus
  conflict_status: ValidationStatus
  failure_reasons: string[]
  warning_reasons: string[]
  geometry_metrics: Record<string, any>
  topology_metrics: Record<string, any>
  area_metrics: Record<string, any>
  semantic_metrics: Record<string, any>
  conflict_metrics: Record<string, any>
  idempotency_key: string
  created_at: string
  updated_at: string
}

export interface ValidationSummary {
  project_id: string
  total_validated: number
  pass_count: number
  warning_count: number
  fail_count: number
  geometry_failures: number
  topology_failures: number
  area_failures: number
  semantic_failures: number
  conflict_failures: number
  counts_by_status: Record<string, number>
  counts_by_category: Record<string, number>
}

export interface ValidationResultListResponse {
  items: ValidationResult[]
  total: number
  skip: number
  limit: number
  summary?: ValidationSummary | null
}

export interface ValidationRunRequest {
  area_tolerance_pct?: number
  area_warning_threshold_pct?: number
  check_topology?: boolean
  check_semantics?: boolean
  consume_conflicts?: boolean
}

export interface ValidationRunResponse {
  stage_id: string
  stage_number: number
  status: string
  project_id: string
  records_validated: number
  pass_count: number
  warning_count: number
  fail_count: number
  geometry_failures_count: number
  topology_failures_count: number
  area_failures_count: number
  semantic_failures_count: number
  conflict_failures_count: number
  results_created: number
  results_updated: number
  execution_time_ms: number
}

// ---------------------------------------------------------------------------
// Milestone 10: Stage 10 Confidence Scoring Types
// ---------------------------------------------------------------------------

export type ConfidenceBucket = 'HIGH' | 'MEDIUM' | 'LOW' | 'AMBIGUOUS'
export type ConfidenceReviewStatus = 'AUTO_CONFIRMED' | 'PENDING' | 'FLAGGED' | 'REQUIRES_REVIEW'

export interface ConfidenceRecordItem {
  id: string
  project_id: string
  source_feature_id: string
  candidate_feature_id?: string | null
  source_identifier: string
  candidate_identifier?: string | null
  overall_confidence: number
  confidence_bucket: ConfidenceBucket
  review_status: string
  spatial_score: number
  geometry_score: number
  attribute_score: number
  temporal_score: number
  weights: {
    spatial: number
    geometry: number
    attribute: number
    temporal: number
    [key: string]: number
  }
  contributions: {
    spatial: number
    geometry: number
    attribute: number
    temporal: number
    [key: string]: number
  }
  is_ambiguous: boolean
  critical_conflict_count: number
  validation_status?: string | null
  reasons: string[]
  created_at?: string
}

export interface ConfidenceSummary {
  project_id: string
  total_records_scored: number
  high_count: number
  medium_count: number
  low_count: number
  ambiguous_count: number
  review_required_count: number
  auto_confirmed_count: number
  average_confidence: number
  counts_by_bucket: Record<string, number>
  counts_by_review_status: Record<string, number>
}

export interface ConfidenceResultListResponse {
  items: ConfidenceRecordItem[]
  total: number
  skip: number
  limit: number
  summary?: ConfidenceSummary | null
}

export interface ConfidenceScoringRunRequest {
  spatial_weight?: number
  geometry_weight?: number
  attribute_weight?: number
  temporal_weight?: number
  high_threshold?: number
  medium_threshold?: number
  enforce_validation_constraints?: boolean
  enforce_conflict_constraints?: boolean
}

export interface ConfidenceScoringRunResponse {
  stage_id: string
  stage_number: number
  status: string
  project_id: string
  records_scored: number
  high_count: number
  medium_count: number
  low_count: number
  ambiguous_count: number
  review_required_count: number
  auto_confirmed_count: number
  average_confidence: number
  execution_time_ms: number
  weights_applied: Record<string, number>
}

// ---------------------------------------------------------------------------
// Pipeline Stage 11: Human Review & Adjudication Types
// ---------------------------------------------------------------------------

export type AdjudicationActionType =
  | 'ACCEPT_SOURCE_A'
  | 'ACCEPT_SOURCE_B'
  | 'MERGE_RECONCILE'
  | 'REJECT_UNRESOLVED'

export interface ReviewQueueConflictItem {
  id: string
  conflict_type: string
  category: string
  severity: string
  severity_reason?: string | null
  status: string
  field_name: string
  source_a: string
  source_b: string
  value_a?: string | null
  value_b?: string | null
  discrepancy_value?: string | null
  discrepancy_percentage?: number | null
  explanation?: string | null
}

export interface AdjudicationQueueItem {
  id: string
  harmonized_record_id: string
  project_id: string
  source_identifier: string
  candidate_identifier: string
  source_feature_id?: string | null
  candidate_feature_id?: string | null
  feature_match_id?: string | null
  overall_confidence: number
  confidence_bucket: string
  bucket_label: string
  confidence_explanation?: string | null
  signal_contributions: Record<string, number>
  reasons: string[]
  validation_status: string
  validation_failure_reasons: string[]
  validation_warning_reasons: string[]
  conflict_count: number
  highest_conflict_severity?: string | null
  has_critical_conflicts: boolean
  conflicts: ReviewQueueConflictItem[]
  spatial_metrics: Record<string, any>
  source_attributes: Record<string, any>
  candidate_attributes: Record<string, any>
  harmonized_attributes: Record<string, any>
  review_status: string
  adjudication_status: string
  adjudication_action?: AdjudicationActionType | null
  authoritative_geometry_source?: string | null
  authoritative_attributes: Record<string, any>
  reviewer_name?: string | null
  notes?: string | null
  adjudicated_at?: string | null
  override_applied: boolean
  requires_mandatory_review: boolean
}

export type Stage11ReviewQueueItem = AdjudicationQueueItem

export interface ReviewQueueSummary {
  project_id: string
  total_review_items: number
  unresolved_count: number
  resolved_count: number
  critical_count: number
  high_conflict_count: number
  medium_conflict_count: number
  low_conflict_count: number
  accept_source_a_count: number
  accept_source_b_count: number
  merged_count: number
  rejected_count: number
  average_confidence: number
  stage_status: string
  is_completed: boolean
  completion_progress_pct: number
  last_adjudication_at?: string | null
}

export interface ReviewQueueListResponse {
  items: AdjudicationQueueItem[]
  total: number
  page: number
  page_size: number
}

export interface AdjudicationActionRequest {
  action: AdjudicationActionType
  notes?: string | null
  reviewer_name?: string | null
  authoritative_geometry_source?: 'SOURCE_A' | 'SOURCE_B' | 'CUSTOM' | null
  authoritative_attributes?: Record<string, any>
}

export interface AdjudicationActionResponse {
  success: boolean
  record_id: string
  action: string
  status: string
  decision: AdjudicationQueueItem
  summary: ReviewQueueSummary
  stage_status: string
  is_stage_completed: boolean
  message: string
}

export interface Stage11ExecutionResponse {
  stage_number: number
  stage_id: string
  status: string
  records_adjudicated: number
  records_pending: number
  summary: ReviewQueueSummary
  message: string
}





