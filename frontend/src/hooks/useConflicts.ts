import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { useAppStore } from '../stores/useAppStore'
import type {
  ConflictResolveInput,
  ConflictDismissInput,
  AttributeConflict,
} from '../types'

export function useRecordConflicts(recordId?: string) {
  return useQuery({
    queryKey: ['record-conflicts', recordId],
    queryFn: () => api.getRecordConflicts(recordId!),
    enabled: Boolean(recordId),
  })
}

export function useProjectConflicts(
  projectId?: string,
  params?: {
    status?: string
    attribute_name?: string
    severity?: string
    skip?: number
    limit?: number
  }
) {
  return useQuery({
    queryKey: ['project-conflicts', projectId, params],
    queryFn: () => api.getProjectConflicts(projectId!, params),
    enabled: Boolean(projectId),
  })
}

export function useProjectConflictSummary(projectId?: string) {
  return useQuery({
    queryKey: ['project-conflict-summary', projectId],
    queryFn: () => api.getProjectConflictSummary(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useConflictDetail(conflictId?: string) {
  return useQuery({
    queryKey: ['conflict-detail', conflictId],
    queryFn: () => api.getConflictDetail(conflictId!),
    enabled: Boolean(conflictId),
  })
}

export function useResolveConflict(projectId?: string, recordId?: string) {
  const queryClient = useQueryClient()
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation({
    mutationFn: ({
      conflictId,
      input,
    }: {
      conflictId: string
      input: ConflictResolveInput
    }) => api.resolveConflict(conflictId, input),
    onSuccess: (data: AttributeConflict) => {
      queryClient.invalidateQueries({ queryKey: ['record-conflicts', recordId] })
      queryClient.invalidateQueries({ queryKey: ['project-conflicts', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-conflict-summary', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-record', recordId] })
      queryClient.invalidateQueries({ queryKey: ['unified-records', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-statistics', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-record-provenance', recordId] })
      showNotification(
        'success',
        `Conflict on '${data.attribute_name}' successfully resolved.`
      )
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.error?.message ||
        err.message ||
        'Failed to resolve attribute conflict.'
      showNotification('error', msg)
    },
  })
}

export function useDismissConflict(projectId?: string, recordId?: string) {
  const queryClient = useQueryClient()
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation({
    mutationFn: ({
      conflictId,
      input,
    }: {
      conflictId: string
      input: ConflictDismissInput
    }) => api.dismissConflict(conflictId, input),
    onSuccess: (data: AttributeConflict) => {
      queryClient.invalidateQueries({ queryKey: ['record-conflicts', recordId] })
      queryClient.invalidateQueries({ queryKey: ['project-conflicts', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-conflict-summary', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-record', recordId] })
      queryClient.invalidateQueries({ queryKey: ['unified-records', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-statistics', projectId] })
      queryClient.invalidateQueries({ queryKey: ['unified-record-provenance', recordId] })
      showNotification(
        'success',
        `Conflict on '${data.attribute_name}' dismissed with audit note.`
      )
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.error?.message ||
        err.message ||
        'Failed to dismiss attribute conflict.'
      showNotification('error', msg)
    },
  })
}
