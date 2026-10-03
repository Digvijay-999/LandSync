import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type {
  CandidateGenerationRequest,
  CandidateGenerationResponse,
  FeatureMatchingRunRequest,
  FeatureMatchingRunResponse,
  HarmonizationRunRequest,
  HarmonizationRunResponse,
  ConflictDetectionRunRequest,
  ConflictDetectionRunResponse,
  GeospatialConflictListResponse,
  GeospatialConflict,
  PipelineStatusResponse,
  ValidationRunRequest,
  ValidationRunResponse,
  ValidationResultListResponse,
  ValidationSummary,
  ValidationResult,
  ConfidenceScoringRunRequest,
  ConfidenceScoringRunResponse,
  ConfidenceResultListResponse,
  ConfidenceSummary,
  ConfidenceRecordItem,
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
  ProjectProvenanceSummaryResponse,
  ProvenanceRecordDetailResponse,
  Stage14ExecutionResponse,
  Stage14StatusResponse,
  ExportCreateRequest,
  ExportJobItem,
  ExportJobListResponse,
  ExportManifestResponse,
} from '../types'

export function usePipelineStatus(projectId?: string) {
  return useQuery<PipelineStatusResponse>({
    queryKey: ['pipeline-status', projectId],
    queryFn: () => api.getPipelineStatus(projectId!),
    enabled: Boolean(projectId),
    refetchInterval: 10000,
  })
}

export function useRunCandidateGeneration(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<CandidateGenerationResponse, Error, CandidateGenerationRequest | undefined>({
    mutationFn: (params) => api.runCandidateGeneration(projectId!, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-layers', projectId] })
      queryClient.invalidateQueries({ queryKey: ['datasets', projectId] })
    },
  })
}

export function useRunFeatureMatching(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<FeatureMatchingRunResponse, Error, FeatureMatchingRunRequest | undefined>({
    mutationFn: (params) => api.runFeatureMatching(projectId!, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['matching-runs', projectId] })
      queryClient.invalidateQueries({ queryKey: ['reconciliation', projectId] })
      queryClient.invalidateQueries({ queryKey: ['conflicts', projectId] })
    },
  })
}

export function useRunHarmonization(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<HarmonizationRunResponse, Error, HarmonizationRunRequest | undefined>({
    mutationFn: (params) => api.runHarmonization(projectId!, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-records', projectId] })
      queryClient.invalidateQueries({ queryKey: ['conflicts', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-layers', projectId] })
    },
  })
}

export function useRunConflictDetection(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<ConflictDetectionRunResponse, Error, ConflictDetectionRunRequest | undefined>({
    mutationFn: (params) => api.runConflictDetection(projectId!, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['conflicts', projectId] })
      queryClient.invalidateQueries({ queryKey: ['geospatial-conflicts', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-layers', projectId] })
    },
  })
}

export function useGeospatialConflicts(
  projectId?: string,
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
) {
  return useQuery<GeospatialConflictListResponse>({
    queryKey: ['geospatial-conflicts', projectId, params],
    queryFn: () => api.getGeospatialConflicts(projectId!, params),
    enabled: Boolean(projectId),
  })
}

export function useUpdateConflictStatus(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<
    GeospatialConflict,
    Error,
    { conflictId: string; status: string; notes?: string }
  >({
    mutationFn: ({ conflictId, status, notes }) =>
      api.updateConflictStatus(conflictId, status, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['geospatial-conflicts', projectId] })
      queryClient.invalidateQueries({ queryKey: ['conflicts', projectId] })
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
    },
  })
}

export function useRunValidation(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<ValidationRunResponse, Error, ValidationRunRequest | undefined>({
    mutationFn: (params) => api.runValidation(projectId!, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['validation-results', projectId] })
      queryClient.invalidateQueries({ queryKey: ['validation-summary', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-records', projectId] })
      queryClient.invalidateQueries({ queryKey: ['conflicts', projectId] })
    },
  })
}

export function useValidationResults(
  projectId?: string,
  params?: {
    status?: string
    category?: string
    search?: string
    skip?: number
    limit?: number
  }
) {
  return useQuery<ValidationResultListResponse>({
    queryKey: ['validation-results', projectId, params],
    queryFn: () => api.getValidationResults(projectId!, params),
    enabled: Boolean(projectId),
  })
}

export function useValidationSummary(projectId?: string) {
  return useQuery<ValidationSummary>({
    queryKey: ['validation-summary', projectId],
    queryFn: () => api.getValidationSummary(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useValidationResultDetail(resultId?: string) {
  return useQuery<ValidationResult>({
    queryKey: ['validation-result-detail', resultId],
    queryFn: () => api.getValidationResultDetail(resultId!),
    enabled: Boolean(resultId),
  })
}

export function useRunConfidenceScoring(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<ConfidenceScoringRunResponse, Error, ConfidenceScoringRunRequest | undefined>({
    mutationFn: (params) => api.runConfidenceScoring(projectId!, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['confidence-results', projectId] })
      queryClient.invalidateQueries({ queryKey: ['confidence-summary', projectId] })
      queryClient.invalidateQueries({ queryKey: ['matching-runs', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-records', projectId] })
    },
  })
}

export function useConfidenceResults(
  projectId?: string,
  params?: {
    bucket?: string
    review_status?: string
    search?: string
    skip?: number
    limit?: number
  }
) {
  return useQuery<ConfidenceResultListResponse>({
    queryKey: ['confidence-results', projectId, params],
    queryFn: () => api.getConfidenceResults(projectId!, params),
    enabled: Boolean(projectId),
  })
}

export function useConfidenceSummary(projectId?: string) {
  return useQuery<ConfidenceSummary>({
    queryKey: ['confidence-summary', projectId],
    queryFn: () => api.getConfidenceSummary(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useConfidenceDetail(recordId?: string) {
  return useQuery<ConfidenceRecordItem>({
    queryKey: ['confidence-detail', recordId],
    queryFn: () => api.getConfidenceResultDetail(recordId!),
    enabled: Boolean(recordId),
  })
}

export function useReviewSummary(projectId?: string) {
  return useQuery<ReviewQueueSummary>({
    queryKey: ['review-summary', projectId],
    queryFn: () => api.getReviewSummary(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useReviewQueue(
  projectId?: string,
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
) {
  return useQuery<ReviewQueueListResponse>({
    queryKey: ['review-queue', projectId, params],
    queryFn: () => api.getAdjudicationQueue(projectId!, params),
    enabled: Boolean(projectId),
  })
}

export function useReviewItemDetail(projectId?: string, recordId?: string) {
  return useQuery<AdjudicationQueueItem>({
    queryKey: ['review-item-detail', projectId, recordId],
    queryFn: () => api.getAdjudicationItemDetail(projectId!, recordId!),
    enabled: Boolean(projectId && recordId),
  })
}

export function useSubmitAdjudication(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<
    AdjudicationActionResponse,
    Error,
    { recordId: string; payload: AdjudicationActionRequest }
  >({
    mutationFn: ({ recordId, payload }) =>
      api.submitAdjudication(projectId!, recordId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review-summary', projectId] })
      queryClient.invalidateQueries({ queryKey: ['review-queue', projectId] })
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['confidence-summary', projectId] })
      queryClient.invalidateQueries({ queryKey: ['confidence-results', projectId] })
      queryClient.invalidateQueries({ queryKey: ['geospatial-conflicts', projectId] })
      queryClient.invalidateQueries({ queryKey: ['matching-runs', projectId] })
    },
  })
}

export function useFinalizeStage11(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<Stage11ExecutionResponse, Error, void>({
    mutationFn: () => api.finalizeStage11(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['review-summary', projectId] })
      queryClient.invalidateQueries({ queryKey: ['review-queue', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-records', projectId] })
    },
  })
}

export function useStage12Status(projectId?: string) {
  return useQuery<Stage12StatusResponse>({
    queryKey: ['stage-12-status', projectId],
    queryFn: () => api.getStage12Status(projectId!),
    enabled: Boolean(projectId),
    refetchInterval: 5000,
  })
}

export function useRunStage12(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<Stage12ExecutionResponse, Error, void>({
    mutationFn: () => api.executeStage12(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['stage-12-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-records', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-record-statistics', projectId] })
    },
  })
}

export function useStage13Status(projectId?: string) {
  return useQuery<Stage13StatusResponse>({
    queryKey: ['stage-13-status', projectId],
    queryFn: () => api.getStage13Status(projectId!),
    enabled: Boolean(projectId),
    refetchInterval: 5000,
  })
}

export function useRunStage13(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<Stage13ExecutionResponse, Error, void>({
    mutationFn: () => api.executeStage13(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['stage-13-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-provenance', projectId] })
      queryClient.invalidateQueries({ queryKey: ['provenance-summary', projectId] })
    },
  })
}

export function useProjectProvenance(
  projectId?: string,
  params?: { skip?: number; limit?: number; status_filter?: string; search?: string }
) {
  return useQuery<ProjectProvenanceSummaryResponse>({
    queryKey: ['project-provenance', projectId, params],
    queryFn: () => api.getProjectProvenance(projectId!, params),
    enabled: Boolean(projectId),
  })
}

export function useProvenanceRecordDetail(projectId?: string, unifiedRecordId?: string | null) {
  return useQuery<ProvenanceRecordDetailResponse>({
    queryKey: ['provenance-record-detail', projectId, unifiedRecordId],
    queryFn: () => api.getProvenanceRecordDetail(projectId!, unifiedRecordId!),
    enabled: Boolean(projectId && unifiedRecordId),
  })
}

// ---------------------------------------------------------------------------
// Stage 14: Export & Deliverables Hooks
// ---------------------------------------------------------------------------

export function useStage14Status(projectId?: string) {
  return useQuery<Stage14StatusResponse>({
    queryKey: ['stage-14-status', projectId],
    queryFn: () => api.getStage14Status(projectId!),
    enabled: Boolean(projectId),
    refetchInterval: 5000,
  })
}

export function useRunStage14(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<Stage14ExecutionResponse, Error, void>({
    mutationFn: () => api.executeStage14(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['stage-14-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-exports', projectId] })
    },
  })
}

export function useProjectExports(projectId?: string) {
  return useQuery<ExportJobListResponse>({
    queryKey: ['project-exports', projectId],
    queryFn: () => api.getProjectExports(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useCreateExportJob(projectId?: string) {
  const queryClient = useQueryClient()

  return useMutation<ExportJobItem, Error, ExportCreateRequest>({
    mutationFn: (req) => api.createExportJob(projectId!, req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stage-14-status', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-exports', projectId] })
      queryClient.invalidateQueries({ queryKey: ['pipeline-status', projectId] })
    },
  })
}






