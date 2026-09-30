import React, { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  ShieldCheck,
  AlertTriangle,
  HelpCircle,
  RefreshCw,
  Loader2,
  Layers,
  Sparkles,
  GitBranch,
  Scale,
  Plane,
  Building,
  CheckCircle2,
  Sliders,
  Filter,
  Download,
  FileCode,
  FileSpreadsheet,
} from 'lucide-react'
import { useProject } from '../hooks/useProjects'
import {
  useUnifiedRecords,
  useUnifiedRecordStatistics,
  useUnifiedRecord,
  useBuildUnifiedRecords,
} from '../hooks/useUnified'
import { useProjectConflictSummary } from '../hooks/useConflicts'
import { api } from '../services/api'
import { useAppStore } from '../stores/useAppStore'
import { downloadBlob } from '../lib/utils'
import type { UnifiedRecordListItem, UnifiedRecordStatus } from '../types'
import { UnifiedRecordMap } from '../components/unified/UnifiedRecordMap'
import { UnifiedDetailPanel } from '../components/unified/UnifiedDetailPanel'

export const UnifiedRecordsPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const safeProjectId = projectId || ''

  const { data: project, isLoading: projectLoading } = useProject(safeProjectId)

  // Status Filter
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null)

  // Unified Records Query
  const {
    data: recordsData,
    isLoading: recordsLoading,
    refetch: refetchRecords,
  } = useUnifiedRecords(safeProjectId, {
    status: selectedStatus || undefined,
    skip: 0,
    limit: 100,
  })
  const records = recordsData?.items || []

  // Statistics Query
  const {
    data: stats,
    isLoading: statsLoading,
    refetch: refetchStats,
  } = useUnifiedRecordStatistics(safeProjectId)

  // Conflict Summary Query
  const { data: conflictSummary, refetch: refetchConflicts } = useProjectConflictSummary(safeProjectId)

  // Selected Record
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null)

  // Auto-select first record if none selected
  useEffect(() => {
    if (!selectedRecordId && records.length > 0) {
      setSelectedRecordId(records[0].id)
    }
  }, [records, selectedRecordId])

  // Selected Record Detail Query
  const { data: recordDetail, isLoading: detailLoading } = useUnifiedRecord(
    selectedRecordId || undefined
  )

  // Build / Refresh Records Mutation
  const buildMutation = useBuildUnifiedRecords(safeProjectId)

  // Map toggle for Source Footprints
  const [showSourceFootprints, setShowSourceFootprints] = useState(true)

  // Export State
  const [exportingFormat, setExportingFormat] = useState<string | null>(null)
  const showNotification = useAppStore((state) => state.showNotification)

  const handleExportProject = async (format: 'geojson' | 'csv') => {
    setExportingFormat(format)
    try {
      const dateStr = new Date().toISOString().slice(0, 10)
      if (format === 'geojson') {
        const blob = await api.exportProjectGeoJSON(safeProjectId)
        downloadBlob(blob, `landsync-unified-records-${dateStr}.geojson`)
      } else {
        const blob = await api.exportProjectCSV(safeProjectId)
        downloadBlob(blob, `landsync-unified-records-${dateStr}.csv`)
      }
      showNotification('success', `Exported project unified records as ${format.toUpperCase()}`)
    } catch (err: any) {
      showNotification('error', `Failed to export ${format.toUpperCase()}: ${err.message}`)
    } finally {
      setExportingFormat(null)
    }
  }

  const handleRefreshAll = () => {
    refetchRecords()
    refetchStats()
    refetchConflicts()
  }

  if (projectLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] text-slate-400 font-mono">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-400 mb-2" />
        <span>Loading unified records workspace...</span>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="p-8 text-center text-slate-400 font-mono">
        <p>Project not found.</p>
        <Link to="/projects" className="text-cyan-400 underline mt-2 inline-block">
          Return to Projects
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)] bg-surface-950 font-mono text-slate-200 select-none overflow-hidden">
      {/* 1. Header Toolbar */}
      <div className="h-13 bg-surface-900 border-b border-border px-4 py-2 flex items-center justify-between z-20 flex-shrink-0">
        <div className="flex items-center gap-3">
          <Link
            to={`/projects/${safeProjectId}`}
            className="p-1.5 rounded-md hover:bg-surface-800 text-slate-400 hover:text-slate-200 transition-colors"
            title="Back to Project Overview"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wider text-emerald-400 font-bold">
                Unified Land Records
              </span>
              <span className="text-slate-600">/</span>
              <span className="text-xs font-semibold text-slate-200">{project.name}</span>
            </div>
            <div className="text-[10px] text-slate-400 flex items-center gap-2">
              <span>Canonical CRS: <strong className="text-cyan-300">{project.target_crs}</strong></span>
              <span className="text-slate-600">•</span>
              <span>{stats?.total_records || 0} Records Built</span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5">
          <Link
            to={`/projects/${safeProjectId}/reconciliation`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-surface-850 hover:bg-surface-800 border border-border text-cyan-300 hover:text-cyan-200 text-xs font-semibold transition-colors"
            title="Go to Human Review Workspace"
          >
            <GitBranch className="w-3.5 h-3.5 text-cyan-400" />
            <span>Review Queue</span>
          </Link>

          <button
            onClick={handleRefreshAll}
            title="Refresh records and metrics"
            className="p-1.5 rounded bg-surface-850 hover:bg-surface-800 border border-border text-slate-400 hover:text-slate-200 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => buildMutation.mutate()}
            disabled={buildMutation.isPending}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-500 hover:bg-emerald-400 text-surface-950 font-bold text-xs shadow-md transition-all active:scale-[0.98] disabled:opacity-50"
          >
            {buildMutation.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-surface-950" />
            ) : (
              <Sparkles className="w-3.5 h-3.5 fill-current" />
            )}
            <span>Build / Refresh Records</span>
          </button>

          {/* Project Exports */}
          <div className="flex items-center gap-1.5 border-l border-border pl-2.5">
            <button
              onClick={() => handleExportProject('geojson')}
              disabled={Boolean(exportingFormat) || records.length === 0}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-surface-850 hover:bg-surface-800 border border-border text-emerald-400 hover:text-emerald-300 text-xs font-semibold transition-colors disabled:opacity-50"
              title="Export all unified records as GeoJSON"
            >
              {exportingFormat === 'geojson' ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FileCode className="w-3.5 h-3.5" />
              )}
              <span>Export GeoJSON</span>
            </button>

            <button
              onClick={() => handleExportProject('csv')}
              disabled={Boolean(exportingFormat) || records.length === 0}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-surface-850 hover:bg-surface-800 border border-border text-cyan-400 hover:text-cyan-300 text-xs font-semibold transition-colors disabled:opacity-50"
              title="Export all unified records as CSV"
            >
              {exportingFormat === 'csv' ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FileSpreadsheet className="w-3.5 h-3.5" />
              )}
              <span>Export CSV</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. Run Metric Summary Banner (Live DB Metrics) */}
      <div className="h-10 bg-surface-950 border-b border-border px-4 flex items-center justify-between text-xs flex-shrink-0">
        <div className="flex items-center gap-5 overflow-x-auto py-1">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 text-[10px] uppercase font-bold">Total Unified:</span>
            <span className="font-bold text-slate-200 font-mono">
              {stats?.total_records ?? 0}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-emerald-400 text-[10px] uppercase font-bold">Active:</span>
            <span className="font-bold text-emerald-300 font-mono">
              {stats?.active ?? 0}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
            <span className="text-red-400 text-[10px] uppercase font-bold">Conflicts:</span>
            <span className="font-bold text-red-300 font-mono">
              {stats?.conflict ?? 0}
            </span>
            {conflictSummary && conflictSummary.unresolved_conflicts > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[9px] bg-red-950 text-red-300 border border-red-700 animate-pulse font-bold">
                {conflictSummary.unresolved_conflicts} Open
              </span>
            )}
            {conflictSummary && conflictSummary.resolved_conflicts > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[9px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-bold">
                {conflictSummary.resolved_conflicts} Resolved
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-amber-400 text-[10px] uppercase font-bold">Incomplete:</span>
            <span className="font-bold text-amber-300 font-mono">
              {stats?.incomplete ?? 0}
            </span>
          </div>

          <div className="hidden md:flex items-center gap-1.5 pl-3 border-l border-border/80">
            <span className="text-slate-500 text-[10px] uppercase font-bold">Avg Sources:</span>
            <span className="font-bold text-cyan-300 font-mono">
              {stats?.average_sources_per_record ?? 0} / rec
            </span>
          </div>

          <div className="hidden lg:flex items-center gap-4 pl-3 border-l border-border/80 text-[10px]">
            <div className="flex items-center gap-1">
              <Scale className="w-3 h-3 text-cyan-400" />
              <span className="text-slate-400">Cadastral:</span>
              <span className="font-bold text-slate-200 font-mono">{stats?.records_with_cadastral ?? 0}</span>
            </div>
            <div className="flex items-center gap-1">
              <Plane className="w-3 h-3 text-amber-400" />
              <span className="text-slate-400">Drone:</span>
              <span className="font-bold text-slate-200 font-mono">{stats?.records_with_drone ?? 0}</span>
            </div>
            <div className="flex items-center gap-1">
              <Building className="w-3 h-3 text-indigo-400" />
              <span className="text-slate-400">Municipal:</span>
              <span className="font-bold text-slate-200 font-mono">{stats?.records_with_municipal ?? 0}</span>
            </div>
          </div>
        </div>

        <div className="hidden xl:flex items-center gap-2 text-[10px] text-slate-500">
          <span>Gate: <strong className="text-slate-400">Human Accepted Matches</strong></span>
          <span>•</span>
          <span>Idempotent PostGIS Layer</span>
        </div>
      </div>

      {/* 3. Main Workspace Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Center Column: Map (Top) & Records List (Bottom) */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Top Half: Interactive MapLibre Map */}
          <div className="flex-1 min-h-[340px] relative">
            <UnifiedRecordMap
              projectId={safeProjectId}
              targetCrs={project.target_crs}
              selectedRecord={recordDetail || null}
              showSourceFootprints={showSourceFootprints}
              onToggleSourceFootprints={() => setShowSourceFootprints(!showSourceFootprints)}
            />
          </div>

          {/* Bottom Half: Records Table */}
          <div className="h-72 flex-shrink-0 flex flex-col bg-surface-900 border-t border-border font-mono text-slate-200">
            {/* Filter Tabs */}
            <div className="flex items-center justify-between px-3 py-1.5 bg-surface-950 border-b border-border flex-shrink-0">
              <div className="flex items-center gap-1 text-[11px]">
                <button
                  onClick={() => setSelectedStatus(null)}
                  className={`px-2.5 py-1 rounded font-medium transition-all ${
                    selectedStatus === null
                      ? 'bg-emerald-950/80 text-emerald-200 border border-emerald-600 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-surface-850 border border-transparent'
                  }`}
                >
                  All ({stats?.total_records ?? 0})
                </button>
                <button
                  onClick={() => setSelectedStatus('ACTIVE')}
                  className={`px-2.5 py-1 rounded font-medium transition-all ${
                    selectedStatus === 'ACTIVE'
                      ? 'bg-emerald-950/80 text-emerald-200 border border-emerald-600 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-surface-850 border border-transparent'
                  }`}
                >
                  Active ({stats?.active ?? 0})
                </button>
                <button
                  onClick={() => setSelectedStatus('CONFLICT')}
                  className={`px-2.5 py-1 rounded font-medium transition-all ${
                    selectedStatus === 'CONFLICT'
                      ? 'bg-red-950/80 text-red-200 border border-red-600 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-surface-850 border border-transparent'
                  }`}
                >
                  Conflict ({stats?.conflict ?? 0})
                </button>
                <button
                  onClick={() => setSelectedStatus('INCOMPLETE')}
                  className={`px-2.5 py-1 rounded font-medium transition-all ${
                    selectedStatus === 'INCOMPLETE'
                      ? 'bg-amber-950/80 text-amber-200 border border-amber-600 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-surface-850 border border-transparent'
                  }`}
                >
                  Incomplete ({stats?.incomplete ?? 0})
                </button>
              </div>

              <div className="text-[10px] text-slate-500">
                <span>Showing {records.length} records</span>
              </div>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-y-auto min-h-0">
              {recordsLoading ? (
                <div className="flex items-center justify-center p-8 text-slate-400 text-xs gap-2">
                  <div className="w-4 h-4 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
                  <span>Loading unified records...</span>
                </div>
              ) : records.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-8 text-center text-slate-500 text-xs">
                  <ShieldCheck className="w-8 h-8 text-slate-600 mb-2" />
                  <p className="font-semibold text-slate-300 mb-1">No Unified Records Built Yet</p>
                  <p className="text-[11px] text-slate-500 max-w-sm mb-3">
                    Unified records are generated from human-accepted candidate matches. Accept matches in the reconciliation workspace, then click "Build / Refresh Records".
                  </p>
                  <button
                    onClick={() => buildMutation.mutate()}
                    disabled={buildMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Build Records Now</span>
                  </button>
                </div>
              ) : (
                <table className="w-full text-left border-collapse text-xs">
                  <thead className="bg-surface-950/90 text-slate-400 text-[10px] uppercase font-bold sticky top-0 z-10 border-b border-border">
                    <tr>
                      <th className="py-2 px-3 w-10 text-center">#</th>
                      <th className="py-2 px-3 w-32">Identifier</th>
                      <th className="py-2 px-3 w-28 text-center">Status</th>
                      <th className="py-2 px-3 w-24 text-center">Sources</th>
                      <th className="py-2 px-3 w-32">Canonical Area</th>
                      <th className="py-2 px-3">Primary Land Use</th>
                      <th className="py-2 px-3">Geometry Source</th>
                      <th className="py-2 px-3 text-right">Updated</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {records.map((r: UnifiedRecordListItem, idx: number) => {
                      const isSelected = r.id === selectedRecordId
                      return (
                        <tr
                          key={r.id}
                          onClick={() => setSelectedRecordId(r.id)}
                          className={`cursor-pointer transition-colors ${
                            isSelected
                              ? 'bg-emerald-950/60 border-l-4 border-l-emerald-400 text-emerald-50'
                              : 'hover:bg-surface-850/70 text-slate-300'
                          }`}
                        >
                          <td className="py-2 px-3 text-center text-[10px] text-slate-500 font-mono">
                            {idx + 1}
                          </td>
                          <td className="py-2 px-3 font-bold font-mono text-emerald-400">
                            {r.record_identifier}
                          </td>
                          <td className="py-2 px-3 text-center">
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                r.status === 'ACTIVE'
                                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-600'
                                  : r.status === 'CONFLICT'
                                  ? 'bg-red-950 text-red-300 border border-red-600'
                                  : 'bg-amber-950 text-amber-300 border border-amber-600'
                              }`}
                            >
                              {r.status}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-center font-bold text-cyan-300 font-mono">
                            {r.source_count}
                          </td>
                          <td className="py-2 px-3 font-mono">
                            {r.area !== null && r.area !== undefined ? `${r.area.toLocaleString()} m²` : '—'}
                          </td>
                          <td className="py-2 px-3 truncate max-w-[140px]">
                            {r.canonical_attributes?.land_use || '—'}
                          </td>
                          <td className="py-2 px-3 text-[10px] text-slate-400">
                            {r.geometry_source_role || 'DEFAULT'}
                          </td>
                          <td className="py-2 px-3 text-right text-[10px] text-slate-500">
                            {new Date(r.updated_at).toLocaleDateString()}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Record Detail Panel */}
        <UnifiedDetailPanel
          record={recordDetail || null}
          isLoading={detailLoading}
          onClose={() => setSelectedRecordId(null)}
        />
      </div>
    </div>
  )
}
