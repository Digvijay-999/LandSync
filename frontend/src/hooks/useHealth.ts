import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export function useHealth(checkDb = true) {
  return useQuery({
    queryKey: ['system-health', checkDb],
    queryFn: () => api.getHealth(checkDb),
    refetchInterval: 15000, // Poll every 15s for live status
    retry: 2,
  })
}
