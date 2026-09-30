import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { useAppStore } from '../stores/useAppStore'
import type { UnifiedRecordBuildResponse } from '../types'

export function useUnifiedRecords(
  projectId?: string,
  params?: {
    status?: string
    skip?: number
    limit?: number
  }
) {
  return useQuery({
    queryKey: ['unified-records', projectId, params],
    queryFn: () => api.getUnifiedRecords(projectId!, params),
    enabled: Boolean(projectId),
  })
}

export function useUnifiedRecordStatistics(projectId?: string) {
  return useQuery({
    queryKey: ['unified-statistics', projectId],
    queryFn: () => api.getUnifiedRecordStatistics(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useUnifiedRecord(recordId?: string) {
  return useQuery({
    queryKey: ['unified-record', recordId],
    queryFn: () => api.getUnifiedRecordDetail(recordId!),
    enabled: Boolean(recordId),
  })
}

export function useUnifiedRecordSources(recordId?: string) {
  return useQuery({
    queryKey: ['unified-record-sources', recordId],
    queryFn: () => api.getUnifiedRecordSources(recordId!),
    enabled: Boolean(recordId),
  })
}

export function useBuildUnifiedRecords(projectId: string) {
  const queryClient = useQueryClient()
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation({
    mutationFn: () => api.buildUnifiedRecords(projectId),
    onSuccess: (data: UnifiedRecordBuildResponse) => {
      queryClient.invalidateQueries({ queryKey: ['unified-records', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-statistics', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-record'] })
      showNotification(
        'success',
        `Unified records synchronized: ${data.records_created} created, ${data.records_updated} updated, ${data.records_unchanged} unchanged (${data.total_records} total).`
      )
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.error?.message ||
        err.message ||
        'Failed to build unified land records.'
      showNotification('error', msg)
    },
  })
}

export function useUnifiedRecordProvenance(recordId?: string) {
  return useQuery({
    queryKey: ['unified-record-provenance', recordId],
    queryFn: () => api.getUnifiedRecordProvenance(recordId!),
    enabled: Boolean(recordId),
  })
}

export function useProjectProvenanceSummary(projectId?: string) {
  return useQuery({
    queryKey: ['project-provenance-summary', projectId],
    queryFn: () => api.getProjectProvenanceSummary(projectId!),
    enabled: Boolean(projectId),
  })
}
