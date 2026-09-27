import { create } from 'zustand'

interface AppState {
  sidebarOpen: boolean
  activeProjectId: string | null
  notification: {
    type: 'success' | 'error' | 'info'
    message: string
  } | null

  // Actions
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setActiveProjectId: (id: string | null) => void
  showNotification: (type: 'success' | 'error' | 'info', message: string) => void
  clearNotification: () => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarOpen: true,
  activeProjectId: null,
  notification: null,

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setActiveProjectId: (id) => set({ activeProjectId: id }),
  showNotification: (type, message) => set({ notification: { type, message } }),
  clearNotification: () => set({ notification: null }),
}))
