import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { useAppStore } from '../stores/useAppStore'
import type { MatchingRunCreateInput } from '../types'

export function useMatchingRuns(projectId?: string, skip = 0, limit = 50) {
  return useQuery({
    queryKey: ['matching-runs', projectId, skip, limit],
    queryFn: () => api.getMatchingRuns(projectId!, skip, limit),
    enabled: Boolean(projectId),
  })
}

export function useMatchingRun(runId?: string) {
  return useQuery({
    queryKey: ['matching-run', runId],
    queryFn: () => api.getMatchingRun(runId!),
    enabled: Boolean(runId),
  })
}

export function useRunMatches(
  runId?: string,
  params?: {
    status?: string
    candidate_role?: string
    is_best_only?: boolean
    min_confidence?: number
    max_confidence?: number
    source_dataset_id?: string
    candidate_dataset_id?: string
    skip?: number
    limit?: number
  }
) {
  return useQuery({
    queryKey: ['run-matches', runId, params],
    queryFn: () => api.getRunMatches(runId!, params),
    enabled: Boolean(runId),
  })
}

export function useSourceFeatureCandidates(runId?: string, sourceFeatureId?: string) {
  return useQuery({
    queryKey: ['source-feature-candidates', runId, sourceFeatureId],
    queryFn: () => api.getSourceFeatureCandidates(runId!, sourceFeatureId!),
    enabled: Boolean(runId && sourceFeatureId),
  })
}

export function useSourceFeatureSummary(runId?: string, sourceFeatureId?: string) {
  return useQuery({
    queryKey: ['source-feature-summary', runId, sourceFeatureId],
    queryFn: () => api.getSourceFeatureSummary(runId!, sourceFeatureId!),
    enabled: Boolean(runId && sourceFeatureId),
  })
}

export function useMatchDetail(matchId?: string) {
  return useQuery({
    queryKey: ['match-detail', matchId],
    queryFn: () => api.getMatchDetail(matchId!),
    enabled: Boolean(matchId),
  })
}

export function useStartMatchingRun(projectId: string) {
  const queryClient = useQueryClient()
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation({
    mutationFn: (input: MatchingRunCreateInput) => api.startMatchingRun(projectId, input),
    onSuccess: (newRun) => {
      queryClient.invalidateQueries({ queryKey: ['matching-runs', projectId] })
      showNotification(
        'success',
        `Matching analysis run completed successfully (${newRun.total_matches} matched, ${newRun.total_possible_matches} possible, ${newRun.total_conflicts} conflicts, ${newRun.total_unmatched} unmatched).`
      )
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.error?.message ||
        err.message ||
        'Failed to execute matching analysis run.'
      showNotification('error', msg)
    },
  })
}

export function useReviewQueue(
  runId?: string,
  params?: {
    category?: string
    skip?: number
    limit?: number
  }
) {
  return useQuery({
    queryKey: ['review-queue', runId, params],
    queryFn: () => api.getReviewQueue(runId!, params),
    enabled: Boolean(runId),
  })
}

export function useReviewStatistics(runId?: string) {
  return useQuery({
    queryKey: ['review-statistics', runId],
    queryFn: () => api.getReviewStatistics(runId!),
    enabled: Boolean(runId),
  })
}

export function useSubmitMatchReview(matchId?: string, runId?: string) {
  const queryClient = useQueryClient()
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation({
    mutationFn: (input: { decision: 'ACCEPTED' | 'REJECTED' | 'FLAGGED'; comment?: string | null }) =>
      api.submitMatchReview(matchId!, input),
    onSuccess: (updatedMatch) => {
      queryClient.invalidateQueries({ queryKey: ['match-detail', matchId] })
      if (runId) {
        queryClient.invalidateQueries({ queryKey: ['review-queue', runId] })
        queryClient.invalidateQueries({ queryKey: ['review-statistics', runId] })
        queryClient.invalidateQueries({ queryKey: ['run-matches', runId] })
        queryClient.invalidateQueries({ queryKey: ['source-feature-candidates', runId] })
        queryClient.invalidateQueries({ queryKey: ['source-feature-summary', runId] })
      } else {
        queryClient.invalidateQueries({ queryKey: ['review-queue'] })
        queryClient.invalidateQueries({ queryKey: ['review-statistics'] })
        queryClient.invalidateQueries({ queryKey: ['run-matches'] })
      }
      showNotification(
        'success',
        `Match decision recorded: ${updatedMatch.review_status}`
      )
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.error?.message ||
        err.message ||
        'Failed to record match review decision.'
      showNotification('error', msg)
    },
  })
}

export function useSeedDemoReviews(runId?: string) {
  const queryClient = useQueryClient()
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation({
    mutationFn: () => api.seedDemoReviews(runId!),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['review-queue', runId] })
      queryClient.invalidateQueries({ queryKey: ['review-statistics', runId] })
      queryClient.invalidateQueries({ queryKey: ['run-matches', runId] })
      queryClient.invalidateQueries({ queryKey: ['match-detail'] })
      showNotification('success', data.message || 'Demo reviews seeded successfully.')
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.error?.message ||
        err.message ||
        'Failed to seed demo reviews.'
      showNotification('error', msg)
    },
  })
}
