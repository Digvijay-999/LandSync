import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { useAppStore } from '../stores/useAppStore'
import type { DatasetUploadInput } from '../types'

export function useProjectDatasets(projectId?: string, skip = 0, limit = 50) {
  return useQuery({
    queryKey: ['datasets', projectId, skip, limit],
    queryFn: () => api.getProjectDatasets(projectId!, skip, limit),
    enabled: Boolean(projectId),
  })
}

export function useDataset(datasetId?: string) {
  return useQuery({
    queryKey: ['dataset', datasetId],
    queryFn: () => api.getDataset(datasetId!),
    enabled: Boolean(datasetId),
  })
}

export function useDatasetProfile(datasetId?: string) {
  return useQuery({
    queryKey: ['dataset-profile', datasetId],
    queryFn: () => api.getDatasetProfile(datasetId!),
    enabled: Boolean(datasetId),
  })
}

export function useUploadDataset(projectId: string) {
  const queryClient = useQueryClient()
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation({
    mutationFn: (input: DatasetUploadInput) =>
      api.uploadDataset(projectId, input.file, input.name, input.crs),
    onSuccess: (newDataset) => {
      queryClient.invalidateQueries({ queryKey: ['datasets', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-layers', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-geojson', projectId] })
      showNotification(
        'success',
        `Dataset "${newDataset.name}" ingested and profiled successfully (${newDataset.feature_count} features).`
      )
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.error?.message ||
        err.message ||
        'Failed to upload and ingest dataset.'
      showNotification('error', msg)
    },
  })
}

export function useDeleteDataset(projectId: string) {
  const queryClient = useQueryClient()
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation({
    mutationFn: (datasetId: string) => api.deleteDataset(datasetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-layers', projectId] })
      queryClient.invalidateQueries({ queryKey: ['project-geojson', projectId] })
      showNotification('success', 'Dataset deleted successfully.')
    },
    onError: (err: any) => {
      const msg =
        err.response?.data?.error?.message ||
        err.message ||
        'Failed to delete dataset.'
      showNotification('error', msg)
    },
  })
}

export function useProjectLayers(projectId?: string) {
  return useQuery({
    queryKey: ['project-layers', projectId],
    queryFn: () => api.getProjectLayers(projectId!),
    enabled: Boolean(projectId),
  })
}

export function useDatasetGeoJSON(
  datasetId?: string,
  representation: 'canonical' | 'source' = 'canonical'
) {
  return useQuery({
    queryKey: ['dataset-geojson', datasetId, representation],
    queryFn: () => api.getDatasetFeaturesGeoJSON(datasetId!, representation),
    enabled: Boolean(datasetId),
    staleTime: 60000,
  })
}

export function useProjectCombinedGeoJSON(projectId?: string) {
  return useQuery({
    queryKey: ['project-geojson', projectId],
    queryFn: () => api.getProjectCombinedGeoJSON(projectId!),
    enabled: Boolean(projectId),
    staleTime: 60000,
  })
}

