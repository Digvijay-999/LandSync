import { create } from 'zustand'

interface AppState {
  sidebarOpen: boolean
  activeProjectId: string | null
  notification: {
    type: 'success' | 'error' | 'info'
    message: string
  } | null

  // Assistant State
  assistantOpen: boolean
  assistantContextRecordId: string | null
  assistantContextConflictId: string | null

  // Actions
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setActiveProjectId: (id: string | null) => void
  showNotification: (type: 'success' | 'error' | 'info', message: string) => void
  clearNotification: () => void

  // Assistant Actions
  toggleAssistant: () => void
  setAssistantOpen: (open: boolean) => void
  openAssistantWithRecord: (recordId: string) => void
  openAssistantWithConflict: (conflictId: string) => void
  closeAssistant: () => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarOpen: true,
  activeProjectId: null,
  notification: null,

  assistantOpen: false,
  assistantContextRecordId: null,
  assistantContextConflictId: null,

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setActiveProjectId: (id) => set({ activeProjectId: id }),
  showNotification: (type, message) => set({ notification: { type, message } }),
  clearNotification: () => set({ notification: null }),

  toggleAssistant: () => set((state) => ({ assistantOpen: !state.assistantOpen })),
  setAssistantOpen: (open) => set({ assistantOpen: open }),
  openAssistantWithRecord: (recordId) =>
    set({
      assistantOpen: true,
      assistantContextRecordId: recordId,
      assistantContextConflictId: null,
    }),
  openAssistantWithConflict: (conflictId) =>
    set({
      assistantOpen: true,
      assistantContextConflictId: conflictId,
      assistantContextRecordId: null,
    }),
  closeAssistant: () =>
    set({
      assistantOpen: false,
      assistantContextRecordId: null,
      assistantContextConflictId: null,
    }),
}))
