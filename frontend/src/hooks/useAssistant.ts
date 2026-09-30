import { useQuery, useMutation } from '@tanstack/react-query'
import { assistantApi } from '../services/api'
import { useAppStore } from '../stores/useAppStore'
import type {
  AssistantQueryRequest,
  AssistantQueryResponse,
  SuggestedQuestionsResponse,
  AssistantHealthResponse,
} from '../types'

export function useAssistantHealth() {
  return useQuery<AssistantHealthResponse>({
    queryKey: ['assistant-health'],
    queryFn: () => assistantApi.getAssistantHealth(),
    staleTime: 60000,
  })
}

export function useSuggestedQuestions(
  projectId?: string,
  contextRecordId?: string | null
) {
  return useQuery<SuggestedQuestionsResponse>({
    queryKey: ['assistant-suggested-questions', projectId, contextRecordId],
    queryFn: () => assistantApi.getSuggestedQuestions(projectId!, contextRecordId),
    enabled: Boolean(projectId),
    staleTime: 30000,
  })
}

export function useAssistantQuery() {
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation<AssistantQueryResponse, Error, AssistantQueryRequest>({
    mutationFn: (request: AssistantQueryRequest) => assistantApi.queryAssistant(request),
    onError: (error) => {
      showNotification(
        'error',
        error.message || 'Assistant query failed. Check backend connectivity.'
      )
    },
  })
}

export function useReindexProject() {
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation({
    mutationFn: (projectId: string) => assistantApi.reindexProject(projectId),
    onSuccess: (data) => {
      showNotification(
        'success',
        `Indexed ${data.documents_indexed} evidence documents into vector store.`
      )
    },
    onError: (error: any) => {
      showNotification(
        'error',
        error.message || 'Failed to reindex project evidence.'
      )
    },
  })
}

export function useSemanticSearch(
  projectId?: string,
  query?: string,
  limit?: number,
  category?: string
) {
  return useQuery({
    queryKey: ['semantic-search', projectId, query, limit, category],
    queryFn: () => assistantApi.semanticSearch(projectId!, query!, limit, category),
    enabled: Boolean(projectId && query && query.trim().length > 0),
    staleTime: 30000,
  })
}
