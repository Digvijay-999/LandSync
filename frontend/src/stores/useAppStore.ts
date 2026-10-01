import { create } from 'zustand'
import type { SpatialAnalysisResult } from '../types'

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

  // Spatial Analysis State
  activeSpatialAnalysis: SpatialAnalysisResult | null
  analysisPanelOpen: boolean
  highlightedFeatureId: string | null

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

  // Spatial Analysis Actions
  setActiveSpatialAnalysis: (analysis: SpatialAnalysisResult | null) => void
  clearActiveSpatialAnalysis: () => void
  setAnalysisPanelOpen: (open: boolean) => void
  toggleAnalysisPanel: () => void
  setHighlightedFeatureId: (id: string | null) => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarOpen: true,
  activeProjectId: null,
  notification: null,

  assistantOpen: false,
  assistantContextRecordId: null,
  assistantContextConflictId: null,

  activeSpatialAnalysis: null,
  analysisPanelOpen: false,
  highlightedFeatureId: null,

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

  setActiveSpatialAnalysis: (analysis) =>
    set({
      activeSpatialAnalysis: analysis,
      // Auto open analysis panel if analysis is set
      analysisPanelOpen: !!analysis,
    }),
  clearActiveSpatialAnalysis: () => set({ activeSpatialAnalysis: null }),
  setAnalysisPanelOpen: (open) => set({ analysisPanelOpen: open }),
  toggleAnalysisPanel: () => set((state) => ({ analysisPanelOpen: !state.analysisPanelOpen })),
  setHighlightedFeatureId: (id) => set({ highlightedFeatureId: id }),
}))
