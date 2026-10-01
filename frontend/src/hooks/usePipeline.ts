import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type {
  CandidateGenerationRequest,
  CandidateGenerationResponse,
  FeatureMatchingRunRequest,
  FeatureMatchingRunResponse,
  HarmonizationRunRequest,
  HarmonizationRunResponse,
  PipelineStatusResponse,
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
