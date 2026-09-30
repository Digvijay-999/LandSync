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
  sources: UnifiedRecordSource[]
  created_at: string
  updated_at: string
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
