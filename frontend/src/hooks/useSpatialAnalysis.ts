import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import type {
  ProximityAnalysisParams,
  BufferAnalysisParams,
  IntersectionAnalysisParams,
  ContainmentAnalysisParams,
  DatasetComparisonParams,
  SpatialConflictAnalysisParams,
  SpatialAnalysisResult,
  DatasetComparisonResult,
  SpatialConflictAnalysisResult,
  VersionComparisonParams,
  VersionComparisonResult,
  AnalysisHistorySummary,
  ConflictResolutionProposal,
} from '../types'

export const useProximityAnalysis = () => {
  return useMutation<SpatialAnalysisResult, Error, ProximityAnalysisParams>({
    mutationFn: (params) => api.executeProximityAnalysis(params),
  })
}

export const useBufferAnalysis = () => {
  return useMutation<SpatialAnalysisResult, Error, BufferAnalysisParams>({
    mutationFn: (params) => api.executeBufferAnalysis(params),
  })
}

export const useIntersectionAnalysis = () => {
  return useMutation<SpatialAnalysisResult, Error, IntersectionAnalysisParams>({
    mutationFn: (params) => api.executeIntersectionAnalysis(params),
  })
}

export const useContainmentAnalysis = () => {
  return useMutation<SpatialAnalysisResult, Error, ContainmentAnalysisParams>({
    mutationFn: (params) => api.executeContainmentAnalysis(params),
  })
}

export const useDatasetComparison = () => {
  return useMutation<DatasetComparisonResult, Error, DatasetComparisonParams>({
    mutationFn: (params) => api.executeDatasetComparison(params),
  })
}

export const useSpatialStatistics = (projectId: string, datasetId?: string) => {
  return useQuery<SpatialAnalysisResult, Error>({
    queryKey: ['spatial-statistics', projectId, datasetId],
    queryFn: () => api.executeSpatialStatistics(projectId, datasetId),
    enabled: !!projectId,
    staleTime: 60000,
  })
}

export const useSpatialConflictAnalysis = () => {
  return useMutation<SpatialConflictAnalysisResult, Error, SpatialConflictAnalysisParams>({
    mutationFn: (params) => api.executeSpatialConflictAnalysis(params),
  })
}

export const useVersionComparison = () => {
  return useMutation<VersionComparisonResult, Error, VersionComparisonParams>({
    mutationFn: (params) => api.executeVersionComparison(params),
  })
}

export const useAnalysisHistory = (projectId?: string) => {
  return useQuery<AnalysisHistorySummary[], Error>({
    queryKey: ['analysis-history', projectId],
    queryFn: () => api.getAnalysisHistory(projectId),
    refetchInterval: 10000,
  })
}

export const useProposeConflictResolution = () => {
  return useMutation<ConflictResolutionProposal, Error, { conflictId: string; projectId: string }>({
    mutationFn: ({ conflictId, projectId }) => api.proposeConflictResolution(conflictId, projectId),
  })
}
