import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type { ProjectCreateInput } from '../types'
import { useAppStore } from '../stores/useAppStore'

export function useProjects(skip = 0, limit = 50) {
  return useQuery({
    queryKey: ['projects', skip, limit],
    queryFn: () => api.getProjects(skip, limit),
  })
}

export function useProject(id?: string) {
  return useQuery({
    queryKey: ['project', id],
    queryFn: () => api.getProject(id!),
    enabled: Boolean(id),
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation({
    mutationFn: (input: ProjectCreateInput) => api.createProject(input),
    onSuccess: (newProject) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      showNotification('success', `Project "${newProject.name}" created successfully.`)
    },
    onError: (err: any) => {
      const msg = err.response?.data?.error?.message || 'Failed to create project.'
      showNotification('error', msg)
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()
  const showNotification = useAppStore((state) => state.showNotification)

  return useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      showNotification('success', 'Project deleted successfully.')
    },
    onError: (err: any) => {
      const msg = err.response?.data?.error?.message || 'Failed to delete project.'
      showNotification('error', msg)
    },
  })
}
