import axios, { AxiosError } from 'axios'
import type {
  HealthResponse,
  Project,
  ProjectCreateInput,
  ProjectListResponse,
  Dataset,
  DatasetListResponse,
  DatasetProfile,
  ProjectLayersResponse,
  GeoJSONFeatureCollection,
  FeatureListResponse,
  MatchRun,
  MatchRunListResponse,
  FeatureMatchListResponse,
  MatchDetailResponse,
  MatchingRunCreateInput,
  SourceFeatureCandidateItem,
  SourceFeatureSummaryResponse,
  ReviewQueueResponse,
  ReviewStatisticsResponse,
  MatchReviewCreateInput,
  UnifiedRecordListItem,
  UnifiedRecordListResponse,
  UnifiedRecordDetail,
  UnifiedRecordBuildResponse,
  UnifiedRecordStatistics,
  UnifiedRecordSource,
  UnifiedRecordProvenance,
  ProjectProvenanceSummary,
  AttributeConflict,
  ConflictResolveInput,
  ConflictDismissInput,
  ConflictListResponse,
  ConflictSummary,
  AssistantQueryRequest,
  AssistantQueryResponse,
  SuggestedQuestionsResponse,
  AssistantHealthResponse,
  ReindexResponse,
  SemanticSearchResult,
  SpatialAnalysisResult,
  DatasetComparisonResult,
  SpatialConflictAnalysisResult,
  ProximityAnalysisParams,
  BufferAnalysisParams,
  IntersectionAnalysisParams,
  ContainmentAnalysisParams,
  DatasetComparisonParams,
  SpatialConflictAnalysisParams,
  VersionComparisonParams,
  VersionComparisonResult,
  AnalysisHistorySummary,
  ConflictResolutionProposal,
  PipelineStageItem,
  PipelineStatusResponse,
  CandidateGenerationRequest,
  CandidateGenerationResponse,
  FeatureMatchingRunRequest,
  FeatureMatchingRunResponse,
  HarmonizationRunRequest,
  HarmonizedRecordPreviewItem,
  HarmonizationRunResponse,
  GeospatialConflict,
  GeospatialConflictListResponse,
  ConflictDetectionRunRequest,
  ConflictDetectionRunResponse,
  ValidationResult,
  ValidationSummary,
  ValidationResultListResponse,
  ValidationRunRequest,
  ValidationRunResponse,
  ConfidenceRecordItem,
  ConfidenceSummary,
  ConfidenceResultListResponse,
  ConfidenceScoringRunRequest,
  ConfidenceScoringRunResponse,
  AdjudicationQueueItem,
  ReviewQueueSummary,
  ReviewQueueListResponse,
  AdjudicationActionRequest,
  AdjudicationActionResponse,
  Stage11ExecutionResponse,
  Stage12ExecutionResponse,
  Stage12StatusResponse,
  Stage13ExecutionResponse,
  Stage13StatusResponse,
  ProvenanceRecordDetailResponse,
  ProjectProvenanceSummaryResponse,
  ProvenanceTimelineItem,
  ProvenanceSourceItem,
  ProvenanceRecordItem,
  Stage14ExecutionResponse,
  Stage14StatusResponse,
  ExportCreateRequest,
  ExportJobItem,
  ExportJobListResponse,
  ExportManifestResponse,
} from '../types'


const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

// Centralized error interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ error?: { message?: string } }>) => {
    const errorMsg =
      error.response?.data?.error?.message ||
      error.message ||
      'An unexpected network error occurred'
    console.error(`[API Error] ${error.config?.method?.toUpperCase()} ${error.config?.url}:`, errorMsg)
    return Promise.reject(error)
  }
)

// ============================================================================
// Milestone 9 — Geospatial Intelligence & Spatial Analysis API
// ============================================================================

export const spatialAnalysisApi = {
  async executeProximityAnalysis(params: ProximityAnalysisParams): Promise<SpatialAnalysisResult> {
    const response = await apiClient.post<SpatialAnalysisResult>('/api/v1/analysis/proximity', params)
    return response.data
  },

  async executeBufferAnalysis(params: BufferAnalysisParams): Promise<SpatialAnalysisResult> {
    const response = await apiClient.post<SpatialAnalysisResult>('/api/v1/analysis/buffer', params)
    return response.data
  },

  async executeIntersectionAnalysis(params: IntersectionAnalysisParams): Promise<SpatialAnalysisResult> {
    const response = await apiClient.post<SpatialAnalysisResult>('/api/v1/analysis/intersection', params)
    return response.data
  },

  async executeContainmentAnalysis(params: ContainmentAnalysisParams): Promise<SpatialAnalysisResult> {
    const response = await apiClient.post<SpatialAnalysisResult>('/api/v1/analysis/containment', params)
    return response.data
  },

  async executeDatasetComparison(params: DatasetComparisonParams): Promise<DatasetComparisonResult> {
    const response = await apiClient.post<DatasetComparisonResult>('/api/v1/analysis/compare', params)
    return response.data
  },

  async executeSpatialStatistics(projectId: string, datasetId?: string): Promise<SpatialAnalysisResult> {
    const response = await apiClient.post<SpatialAnalysisResult>('/api/v1/analysis/statistics', {
      project_id: projectId,
      dataset_id: datasetId || undefined,
    })
    return response.data
  },

  async executeSpatialConflictAnalysis(params: SpatialConflictAnalysisParams): Promise<SpatialConflictAnalysisResult> {
    const response = await apiClient.post<SpatialConflictAnalysisResult>('/api/v1/analysis/conflicts', params)
    return response.data
  },

  async executeVersionComparison(params: VersionComparisonParams): Promise<VersionComparisonResult> {
    const response = await apiClient.post<VersionComparisonResult>('/api/v1/analysis/versions/compare', params)
    return response.data
  },

  async getAnalysisHistory(projectId?: string): Promise<AnalysisHistorySummary[]> {
    const response = await apiClient.get<AnalysisHistorySummary[]>('/api/v1/analysis/history', {
      params: { project_id: projectId },
    })
    return response.data
  },

  async getAnalysisById(analysisId: string): Promise<SpatialAnalysisResult> {
    const response = await apiClient.get<SpatialAnalysisResult>(`/api/v1/analysis/${analysisId}`)
    return response.data
  },

  async exportAnalysisResult(result: SpatialAnalysisResult, format: 'geojson' | 'csv' = 'geojson'): Promise<Blob> {
    const response = await apiClient.post(`/api/v1/analysis/export?format=${format}`, result, {
      responseType: 'blob',
    })
    return response.data
  },

  async exportAnalysisById(analysisId: string, format: 'geojson' | 'csv' = 'geojson'): Promise<Blob> {
    const response = await apiClient.get(`/api/v1/analysis/${analysisId}/export?format=${format}`, {
      responseType: 'blob',
    })
    return response.data
  },

  async proposeConflictResolution(conflictId: string, projectId: string): Promise<ConflictResolutionProposal> {
    const response = await apiClient.post<ConflictResolutionProposal>(
      `/api/v1/conflicts/${conflictId}/propose-resolution`,
      null,
      { params: { project_id: projectId } }
    )
    return response.data
  },
}

// ============================================================================
// Pipeline Workflow & Harmonization Execution API
// ============================================================================

export const pipelineApi = {
  async getPipelineStatus(projectId: string): Promise<PipelineStatusResponse> {
    const response = await apiClient.get<PipelineStatusResponse>(
      `/api/v1/projects/${projectId}/pipeline/status`
    )
    return response.data
  },

  async runCandidateGeneration(
    projectId: string,
    params?: CandidateGenerationRequest
  ): Promise<CandidateGenerationResponse> {
    const response = await apiClient.post<CandidateGenerationResponse>(
      `/api/v1/projects/${projectId}/pipeline/candidate-generation/run`,
      params || {}
    )
    return response.data
  },

  async runFeatureMatching(
    projectId: string,
    params?: FeatureMatchingRunRequest
  ): Promise<FeatureMatchingRunResponse> {
    const response = await apiClient.post<FeatureMatchingRunResponse>(
      `/api/v1/projects/${projectId}/pipeline/feature-matching/run`,
      params || {}
    )
    return response.data
  },

  async runHarmonization(
    projectId: string,
    params?: HarmonizationRunRequest
  ): Promise<HarmonizationRunResponse> {
    const response = await apiClient.post<HarmonizationRunResponse>(
      `/api/v1/projects/${projectId}/pipeline/harmonization/run`,
      params || {}
    )
    return response.data
  },

  async runConflictDetection(
    projectId: string,
    params?: ConflictDetectionRunRequest
  ): Promise<ConflictDetectionRunResponse> {
    const response = await apiClient.post<ConflictDetectionRunResponse>(
      `/api/v1/projects/${projectId}/pipeline/stage-08/execute`,
      params || {}
    )
    return response.data
  },

  async runValidation(
    projectId: string,
    params?: ValidationRunRequest
  ): Promise<ValidationRunResponse> {
    const response = await apiClient.post<ValidationRunResponse>(
      `/api/v1/projects/${projectId}/pipeline/stage-09/execute`,
      params || {}
    )
    return response.data
  },

  async getValidationResults(
    projectId: string,
    params?: {
      status?: string
      category?: string
      search?: string
      skip?: number
      limit?: number
    }
  ): Promise<ValidationResultListResponse> {
    const response = await apiClient.get<ValidationResultListResponse>(
      `/api/v1/projects/${projectId}/validation-results`,
      { params }
    )
    return response.data
  },

  async getValidationSummary(projectId: string): Promise<ValidationSummary> {
    const response = await apiClient.get<ValidationSummary>(
      `/api/v1/projects/${projectId}/validation-summary`
    )
    return response.data
  },

  async getValidationResultDetail(resultId: string): Promise<ValidationResult> {
    const response = await apiClient.get<ValidationResult>(
      `/api/v1/validation-results/${resultId}`
    )
    return response.data
  },

  async runConfidenceScoring(
    projectId: string,
    params?: ConfidenceScoringRunRequest
  ): Promise<ConfidenceScoringRunResponse> {
    const response = await apiClient.post<ConfidenceScoringRunResponse>(
      `/api/v1/projects/${projectId}/pipeline/stage-10/execute`,
      params || {}
    )
    return response.data
  },

  async getConfidenceResults(
    projectId: string,
    params?: {
      bucket?: string
      review_status?: string
      search?: string
      skip?: number
      limit?: number
    }
  ): Promise<ConfidenceResultListResponse> {
    const response = await apiClient.get<ConfidenceResultListResponse>(
      `/api/v1/projects/${projectId}/confidence-results`,
      { params }
    )
    return response.data
  },

  async getConfidenceSummary(projectId: string): Promise<ConfidenceSummary> {
    const response = await apiClient.get<ConfidenceSummary>(
      `/api/v1/projects/${projectId}/confidence-summary`
    )
    return response.data
  },

  async getConfidenceResultDetail(recordId: string): Promise<ConfidenceRecordItem> {
    const response = await apiClient.get<ConfidenceRecordItem>(
      `/api/v1/confidence-results/${recordId}`
    )
    return response.data
  },

  async getReviewSummary(projectId: string): Promise<ReviewQueueSummary> {
    const response = await apiClient.get<ReviewQueueSummary>(
      `/api/v1/projects/${projectId}/review-summary`
    )
    return response.data
  },

  async getAdjudicationQueue(
    projectId: string,
    params?: {
      severity?: string
      conflict_type?: string
      bucket?: string
      validation_status?: string
      adjudication_status?: string
      search?: string
      page?: number
      page_size?: number
    }
  ): Promise<ReviewQueueListResponse> {
    const response = await apiClient.get<ReviewQueueListResponse>(
      `/api/v1/projects/${projectId}/review-queue`,
      { params }
    )
    return response.data
  },

  async getAdjudicationItemDetail(
    projectId: string,
    recordId: string
  ): Promise<AdjudicationQueueItem> {
    const response = await apiClient.get<AdjudicationQueueItem>(
      `/api/v1/projects/${projectId}/review-queue/${recordId}`
    )
    return response.data
  },

  async submitAdjudication(
    projectId: string,
    recordId: string,
    payload: AdjudicationActionRequest
  ): Promise<AdjudicationActionResponse> {
    const response = await apiClient.post<AdjudicationActionResponse>(
      `/api/v1/projects/${projectId}/review-queue/${recordId}/adjudicate`,
      payload
    )
    return response.data
  },

  async finalizeStage11(projectId: string): Promise<Stage11ExecutionResponse> {
    const response = await apiClient.post<Stage11ExecutionResponse>(
      `/api/v1/projects/${projectId}/pipeline/stage-11/execute`
    )
    return response.data
  },

  async executeStage12(projectId: string): Promise<Stage12ExecutionResponse> {
    const response = await apiClient.post<Stage12ExecutionResponse>(
      `/api/v1/projects/${projectId}/pipeline/stage-12/execute`
    )
    return response.data
  },

  async getStage12Status(projectId: string): Promise<Stage12StatusResponse> {
    const response = await apiClient.get<Stage12StatusResponse>(
      `/api/v1/projects/${projectId}/pipeline/stage-12/status`
    )
    return response.data
  },

  async executeStage13(projectId: string): Promise<Stage13ExecutionResponse> {
    const response = await apiClient.post<Stage13ExecutionResponse>(
      `/api/v1/projects/${projectId}/pipeline/stage-13/execute`
    )
    return response.data
  },

  async getStage13Status(projectId: string): Promise<Stage13StatusResponse> {
    const response = await apiClient.get<Stage13StatusResponse>(
      `/api/v1/projects/${projectId}/pipeline/stage-13/status`
    )
    return response.data
  },

  async executeStage14(projectId: string): Promise<Stage14ExecutionResponse> {
    const response = await apiClient.post<Stage14ExecutionResponse>(
      `/api/v1/projects/${projectId}/pipeline/stage-14/execute`
    )
    return response.data
  },

  async getStage14Status(projectId: string): Promise<Stage14StatusResponse> {
    const response = await apiClient.get<Stage14StatusResponse>(
      `/api/v1/projects/${projectId}/pipeline/stage-14/status`
    )
    return response.data
  },

  async createExportJob(
    projectId: string,
    req: ExportCreateRequest
  ): Promise<ExportJobItem> {
    const response = await apiClient.post<ExportJobItem>(
      `/api/v1/projects/${projectId}/exports`,
      req
    )
    return response.data
  },

  async getProjectExports(projectId: string): Promise<ExportJobListResponse> {
    const response = await apiClient.get<ExportJobListResponse>(
      `/api/v1/projects/${projectId}/exports`
    )
    return response.data
  },

  async getExportManifest(
    projectId: string,
    exportId: string
  ): Promise<ExportManifestResponse> {
    const response = await apiClient.get<ExportManifestResponse>(
      `/api/v1/projects/${projectId}/exports/${exportId}/manifest`
    )
    return response.data
  },

  getExportDownloadUrl(projectId: string, exportId: string): string {
    return `${API_BASE_URL}/api/v1/projects/${projectId}/exports/${exportId}/download`
  },

  async getProjectProvenance(
    projectId: string,
    params?: { skip?: number; limit?: number; status_filter?: string; search?: string }
  ): Promise<ProjectProvenanceSummaryResponse> {
    const response = await apiClient.get<ProjectProvenanceSummaryResponse>(
      `/api/v1/projects/${projectId}/provenance`,
      { params }
    )
    return response.data
  },

  async getProvenanceRecordDetail(
    projectId: string,
    unifiedRecordId: string
  ): Promise<ProvenanceRecordDetailResponse> {
    const response = await apiClient.get<ProvenanceRecordDetailResponse>(
      `/api/v1/projects/${projectId}/provenance/${unifiedRecordId}`
    )
    return response.data
  },

  async getProvenanceTimeline(
    projectId: string,
    unifiedRecordId: string
  ): Promise<ProvenanceTimelineItem[]> {
    const response = await apiClient.get<ProvenanceTimelineItem[]>(
      `/api/v1/projects/${projectId}/provenance/${unifiedRecordId}/timeline`
    )
    return response.data
  },

  async getProvenanceSources(
    projectId: string,
    unifiedRecordId: string
  ): Promise<ProvenanceSourceItem[]> {
    const response = await apiClient.get<ProvenanceSourceItem[]>(
      `/api/v1/projects/${projectId}/provenance/${unifiedRecordId}/sources`
    )
    return response.data
  },
}


export const api = {
  ...spatialAnalysisApi,
  ...pipelineApi,

  // System Health
  async getHealth(checkDb = true): Promise<HealthResponse> {
    const response = await apiClient.get<HealthResponse>('/api/health', {
      params: { check_db: checkDb },
    })
    return response.data
  },

  // Projects
  async getProjects(skip = 0, limit = 50): Promise<ProjectListResponse> {
    const response = await apiClient.get<ProjectListResponse>('/api/v1/projects', {
      params: { skip, limit },
    })
    return response.data
  },

  async getProject(id: string): Promise<Project> {
    const response = await apiClient.get<Project>(`/api/v1/projects/${id}`)
    return response.data
  },

  async createProject(input: ProjectCreateInput): Promise<Project> {
    const response = await apiClient.post<Project>('/api/v1/projects', input)
    return response.data
  },

  async deleteProject(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/projects/${id}`)
  },

  // Datasets
  async getProjectDatasets(projectId: string, skip = 0, limit = 50): Promise<DatasetListResponse> {
    const response = await apiClient.get<DatasetListResponse>(`/api/v1/projects/${projectId}/datasets`, {
      params: { skip, limit },
    })
    return response.data
  },

  async getDataset(id: string): Promise<Dataset> {
    const response = await apiClient.get<Dataset>(`/api/v1/datasets/${id}`)
    return response.data
  },

  async getDatasetProfile(id: string): Promise<DatasetProfile> {
    const response = await apiClient.get<DatasetProfile>(`/api/v1/datasets/${id}/profile`)
    return response.data
  },

  async uploadDataset(
    projectId: string,
    file: File,
    name?: string,
    crs?: string
  ): Promise<Dataset> {
    const formData = new FormData()
    formData.append('file', file)
    if (name && name.trim()) {
      formData.append('name', name.trim())
    }
    if (crs && crs.trim()) {
      formData.append('crs', crs.trim())
    }

    const response = await apiClient.post<Dataset>(
      `/api/v1/projects/${projectId}/datasets`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )
    return response.data
  },

  async deleteDataset(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/datasets/${id}`)
  },

  // Spatial Features & Map Layers
  async getProjectLayers(projectId: string): Promise<ProjectLayersResponse> {
    const response = await apiClient.get<ProjectLayersResponse>(`/api/v1/projects/${projectId}/layers`)
    return response.data
  },

  async getDatasetFeaturesGeoJSON(
    datasetId: string,
    representation: 'canonical' | 'source' = 'canonical',
    limit = 5000
  ): Promise<GeoJSONFeatureCollection> {
    const response = await apiClient.get<GeoJSONFeatureCollection>(
      `/api/v1/datasets/${datasetId}/features/geojson`,
      { params: { representation, limit } }
    )
    return response.data
  },

  async getProjectCombinedGeoJSON(projectId: string): Promise<GeoJSONFeatureCollection> {
    const response = await apiClient.get<GeoJSONFeatureCollection>(
      `/api/v1/projects/${projectId}/features/geojson`
    )
    return response.data
  },

  async getDatasetFeatures(
    datasetId: string,
    representation: 'canonical' | 'source' = 'canonical',
    skip = 0,
    limit = 50
  ): Promise<FeatureListResponse> {
    const response = await apiClient.get<FeatureListResponse>(
      `/api/v1/datasets/${datasetId}/features`,
      { params: { representation, skip, limit } }
    )
    return response.data
  },

  // Milestone 3: Feature Matching & Spatial Reconciliation
  async startMatchingRun(projectId: string, input: MatchingRunCreateInput): Promise<MatchRun> {
    const response = await apiClient.post<MatchRun>(
      `/api/v1/projects/${projectId}/matching-runs`,
      input
    )
    return response.data
  },

  async getMatchingRuns(projectId: string, skip = 0, limit = 50): Promise<MatchRunListResponse> {
    const response = await apiClient.get<MatchRunListResponse>(
      `/api/v1/projects/${projectId}/matching-runs`,
      { params: { skip, limit } }
    )
    return response.data
  },

  async getMatchingRun(runId: string): Promise<MatchRun> {
    const response = await apiClient.get<MatchRun>(`/api/v1/matching-runs/${runId}`)
    return response.data
  },

  async getRunMatches(
    runId: string,
    params?: {
      status?: string
      candidate_role?: string
      review_status?: string
      is_best_only?: boolean
      min_confidence?: number
      max_confidence?: number
      source_dataset_id?: string
      candidate_dataset_id?: string
      skip?: number
      limit?: number
    }
  ): Promise<FeatureMatchListResponse> {
    const response = await apiClient.get<FeatureMatchListResponse>(
      `/api/v1/matching-runs/${runId}/matches`,
      { params }
    )
    return response.data
  },

  async getReviewQueue(
    runId: string,
    params?: {
      category?: string
      skip?: number
      limit?: number
    }
  ): Promise<ReviewQueueResponse> {
    const response = await apiClient.get<ReviewQueueResponse>(
      `/api/v1/matching-runs/${runId}/review-queue`,
      { params }
    )
    return response.data
  },

  async getReviewStatistics(runId: string): Promise<ReviewStatisticsResponse> {
    const response = await apiClient.get<ReviewStatisticsResponse>(
      `/api/v1/matching-runs/${runId}/review-statistics`
    )
    return response.data
  },

  async submitMatchReview(
    matchId: string,
    input: MatchReviewCreateInput
  ): Promise<MatchDetailResponse> {
    const response = await apiClient.post<MatchDetailResponse>(
      `/api/v1/matches/${matchId}/review`,
      input
    )
    return response.data
  },

  async seedDemoReviews(runId: string): Promise<{ message: string; seeded_count: number }> {
    const response = await apiClient.post<{ message: string; seeded_count: number }>(
      `/api/v1/matching-runs/${runId}/seed-demo-reviews`
    )
    return response.data
  },

  async getSourceFeatureCandidates(
    runId: string,
    sourceFeatureId: string
  ): Promise<SourceFeatureCandidateItem[]> {
    const response = await apiClient.get<SourceFeatureCandidateItem[]>(
      `/api/v1/matching-runs/${runId}/source-features/${sourceFeatureId}/candidates`
    )
    return response.data
  },

  async getSourceFeatureSummary(
    runId: string,
    sourceFeatureId: string
  ): Promise<SourceFeatureSummaryResponse> {
    const response = await apiClient.get<SourceFeatureSummaryResponse>(
      `/api/v1/matching-runs/${runId}/source-features/${sourceFeatureId}/summary`
    )
    return response.data
  },

  async getMatchDetail(matchId: string): Promise<MatchDetailResponse> {
    const response = await apiClient.get<MatchDetailResponse>(`/api/v1/matches/${matchId}`)
    return response.data
  },

  // ---------------------------------------------------------------------------
  // Milestone 5: Unified Land Records
  // ---------------------------------------------------------------------------

  async buildUnifiedRecords(projectId: string): Promise<UnifiedRecordBuildResponse> {
    const response = await apiClient.post<UnifiedRecordBuildResponse>(
      `/api/v1/projects/${projectId}/unified-records/build`
    )
    return response.data
  },

  async getUnifiedRecords(
    projectId: string,
    params?: { status?: string; resolution_status?: string; search?: string; skip?: number; limit?: number }
  ): Promise<UnifiedRecordListResponse> {
    const response = await apiClient.get<UnifiedRecordListResponse>(
      `/api/v1/projects/${projectId}/unified-records`,
      { params }
    )
    return response.data
  },

  async getUnifiedRecordStatistics(projectId: string): Promise<UnifiedRecordStatistics> {
    const response = await apiClient.get<UnifiedRecordStatistics>(
      `/api/v1/projects/${projectId}/unified-records/statistics`
    )
    return response.data
  },

  async getUnifiedRecordDetail(recordId: string): Promise<UnifiedRecordDetail> {
    const response = await apiClient.get<UnifiedRecordDetail>(
      `/api/v1/unified-records/${recordId}`
    )
    return response.data
  },

  async getUnifiedRecordSources(recordId: string): Promise<UnifiedRecordSource[]> {
    const response = await apiClient.get<UnifiedRecordSource[]>(
      `/api/v1/unified-records/${recordId}/sources`
    )
    return response.data
  },

  // ---------------------------------------------------------------------------
  // Milestone 6: Provenance, Audit Trails & Multi-Format Export
  // ---------------------------------------------------------------------------

  async getUnifiedRecordProvenance(recordId: string): Promise<UnifiedRecordProvenance> {
    const response = await apiClient.get<UnifiedRecordProvenance>(
      `/api/v1/unified-records/${recordId}/provenance`
    )
    return response.data
  },

  async getProjectProvenanceSummary(projectId: string): Promise<ProjectProvenanceSummary> {
    const response = await apiClient.get<ProjectProvenanceSummary>(
      `/api/v1/projects/${projectId}/provenance`
    )
    return response.data
  },

  async exportProjectGeoJSON(projectId: string): Promise<Blob> {
    const response = await apiClient.get(
      `/api/v1/projects/${projectId}/exports/unified-records.geojson`,
      { responseType: 'blob' }
    )
    return response.data
  },

  async exportProjectCSV(projectId: string): Promise<Blob> {
    const response = await apiClient.get(
      `/api/v1/projects/${projectId}/exports/unified-records.csv`,
      { responseType: 'blob' }
    )
    return response.data
  },

  async exportRecordGeoJSON(recordId: string): Promise<Blob> {
    const response = await apiClient.get(
      `/api/v1/unified-records/${recordId}/export.geojson`,
      { responseType: 'blob' }
    )
    return response.data
  },

  async exportRecordCSV(recordId: string): Promise<Blob> {
    const response = await apiClient.get(
      `/api/v1/unified-records/${recordId}/export.csv`,
      { responseType: 'blob' }
    )
    return response.data
  },

  // ---------------------------------------------------------------------------
  // Milestone 7: Attribute Conflict Detection & Reconciliation
  // ---------------------------------------------------------------------------

  async getRecordConflicts(recordId: string): Promise<AttributeConflict[]> {
    const response = await apiClient.get<AttributeConflict[]>(
      `/api/v1/unified-records/${recordId}/conflicts`
    )
    return response.data
  },

  async getProjectConflicts(
    projectId: string,
    params?: {
      status?: string
      attribute_name?: string
      severity?: string
      conflict_type?: string
      category?: string
      source?: string
      search?: string
      skip?: number
      limit?: number
    }
  ): Promise<any> {
    const response = await apiClient.get(
      `/api/v1/projects/${projectId}/conflicts`,
      { params }
    )
    return response.data
  },

  async getGeospatialConflicts(
    projectId: string,
    params?: {
      status?: string
      severity?: string
      conflict_type?: string
      category?: string
      source?: string
      search?: string
      skip?: number
      limit?: number
    }
  ): Promise<GeospatialConflictListResponse> {
    const response = await apiClient.get<GeospatialConflictListResponse>(
      `/api/v1/projects/${projectId}/conflicts`,
      { params }
    )
    return response.data
  },

  async getProjectConflictSummary(projectId: string): Promise<ConflictSummary> {
    const response = await apiClient.get<ConflictSummary>(
      `/api/v1/projects/${projectId}/conflicts/summary`
    )
    return response.data
  },

  async getConflictDetail(conflictId: string): Promise<any> {
    const response = await apiClient.get(
      `/api/v1/conflicts/${conflictId}`
    )
    return response.data
  },

  async updateConflictStatus(
    conflictId: string,
    status: string,
    notes?: string
  ): Promise<GeospatialConflict> {
    const response = await apiClient.patch<GeospatialConflict>(
      `/api/v1/conflicts/${conflictId}`,
      { status, notes }
    )
    return response.data
  },

  async resolveConflict(
    conflictId: string,
    input: ConflictResolveInput
  ): Promise<AttributeConflict> {
    const response = await apiClient.post<AttributeConflict>(
      `/api/v1/conflicts/${conflictId}/resolve`,
      input
    )
    return response.data
  },

  async dismissConflict(
    conflictId: string,
    input: ConflictDismissInput
  ): Promise<AttributeConflict> {
    const response = await apiClient.post<AttributeConflict>(
      `/api/v1/conflicts/${conflictId}/dismiss`,
      input
    )
    return response.data
  },
}

// ============================================================================
// Milestone 8 — AI Geospatial Reasoning & Evidence Assistant API
// ============================================================================

export const assistantApi = {
  async queryAssistant(
    request: AssistantQueryRequest
  ): Promise<AssistantQueryResponse> {
    const response = await apiClient.post<AssistantQueryResponse>(
      '/api/v1/assistant/query',
      request
    )
    return response.data
  },

  async getSuggestedQuestions(
    projectId: string,
    contextRecordId?: string | null
  ): Promise<SuggestedQuestionsResponse> {
    const response = await apiClient.get<SuggestedQuestionsResponse>(
      '/api/v1/assistant/suggested-questions',
      {
        params: {
          project_id: projectId,
          context_record_id: contextRecordId || undefined,
        },
      }
    )
    return response.data
  },

  async getAssistantHealth(): Promise<AssistantHealthResponse> {
    const response = await apiClient.get<AssistantHealthResponse>(
      '/api/v1/assistant/health'
    )
    return response.data
  },

  async reindexProject(projectId: string): Promise<ReindexResponse> {
    const response = await apiClient.post<ReindexResponse>(
      `/api/v1/assistant/projects/${projectId}/reindex`
    )
    return response.data
  },

  async semanticSearch(
    projectId: string,
    query: string,
    limit?: number,
    category?: string
  ): Promise<SemanticSearchResult[]> {
    const response = await apiClient.get<SemanticSearchResult[]>(
      `/api/v1/assistant/projects/${projectId}/semantic-search`,
      {
        params: {
          query,
          limit: limit || 5,
          category: category || undefined,
        },
      }
    )
    return response.data
  },
}



