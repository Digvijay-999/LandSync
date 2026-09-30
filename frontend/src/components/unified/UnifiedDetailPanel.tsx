import React, { useState } from 'react'
import {
  X,
  ShieldCheck,
  AlertTriangle,
  HelpCircle,
  Layers,
  MapPin,
  ExternalLink,
  ChevronRight,
  Database,
  Tag,
  Building,
  Plane,
  Scale,
  Hash,
  Download,
  FileCode,
  FileSpreadsheet,
  Clock,
  GitCommit,
  CheckCircle2,
  FileText,
  Activity,
  History,
  Sparkles,
  Award,
  Ban,
  Check,
  Filter,
} from 'lucide-react'
import type {
  UnifiedRecordDetail,
  UnifiedRecordStatus,
  SourceRole,
  AttributeConflict,
  ConflictSourceValue,
  ConflictStatus,
} from '../../types'
import { useUnifiedRecordProvenance } from '../../hooks/useUnified'
import { useRecordConflicts } from '../../hooks/useConflicts'
import { ConflictResolutionModal } from './ConflictResolutionModal'
import { api } from '../../services/api'
import { downloadBlob, formatDate } from '../../lib/utils'
import { useAppStore } from '../../stores/useAppStore'

interface UnifiedDetailPanelProps {
  record: UnifiedRecordDetail | null
  isLoading: boolean
  onClose: () => void
}

export const UnifiedDetailPanel: React.FC<UnifiedDetailPanelProps> = ({
  record,
  isLoading,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'OVERVIEW' | 'CONFLICTS' | 'PROVENANCE'>('OVERVIEW')
  const [conflictFilter, setConflictFilter] = useState<'ALL' | 'UNRESOLVED' | 'RESOLVED' | 'DISMISSED'>('ALL')
  const [selectedConflictForModal, setSelectedConflictForModal] = useState<AttributeConflict | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [exportingType, setExportingType] = useState<string | null>(null)
  const showNotification = useAppStore((state) => state.showNotification)
  const openAssistantWithRecord = useAppStore((state) => state.openAssistantWithRecord)
  const openAssistantWithConflict = useAppStore((state) => state.openAssistantWithConflict)

  const { data: provenance, isLoading: provLoading } = useUnifiedRecordProvenance(
    record?.id
  )

  const { data: conflictsData, isLoading: conflictsLoading } = useRecordConflicts(
    record?.id
  )

  const handleExportSingle = async (format: 'geojson' | 'csv') => {
    if (!record) return
    setExportingType(format)
    try {
      if (format === 'geojson') {
        const blob = await api.exportRecordGeoJSON(record.id)
        downloadBlob(blob, `landsync-${record.record_identifier}.geojson`)
      } else {
        const blob = await api.exportRecordCSV(record.id)
        downloadBlob(blob, `landsync-${record.record_identifier}.csv`)
      }
      showNotification('success', `Exported ${record.record_identifier} as ${format.toUpperCase()}`)
    } catch (err: any) {
      showNotification('error', `Failed to export ${format.toUpperCase()}: ${err.message}`)
    } finally {
      setExportingType(null)
    }
  }

  const openResolutionModal = (conflict: AttributeConflict) => {
    setSelectedConflictForModal(conflict)
    setIsModalOpen(true)
  }

  if (isLoading) {
    return (
      <div className="w-96 lg:w-[480px] bg-surface-900 border-l border-border flex flex-col items-center justify-center p-8 text-slate-400 font-mono text-xs flex-shrink-0">
        <div className="w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin mb-3" />
        <span>Loading unified land record...</span>
      </div>
    )
  }

  if (!record) {
    return (
      <div className="w-96 lg:w-[480px] bg-surface-900 border-l border-border flex flex-col items-center justify-center p-8 text-center text-slate-500 font-mono text-xs select-none flex-shrink-0">
        <ShieldCheck className="w-8 h-8 text-slate-600 mb-3" />
        <p className="font-semibold text-slate-400 mb-1">No Record Selected</p>
        <p className="text-[11px] leading-relaxed">
          Select a unified land record from the table to inspect its canonical aggregation, contributing source features, and full provenance chain.
        </p>
      </div>
    )
  }

  const {
    record_identifier,
    status,
    geometry_source_role,
    area,
    canonical_attributes = {},
    sources = [],
  } = record

  const conflictsList: AttributeConflict[] = conflictsData || []
  const unresolvedCount = conflictsList.filter((c: AttributeConflict) => c.status === 'UNRESOLVED').length
  const resolvedCount = conflictsList.filter((c: AttributeConflict) => c.status === 'RESOLVED').length
  const dismissedCount = conflictsList.filter((c: AttributeConflict) => c.status === 'DISMISSED').length
  const totalConflicts = conflictsList.length

  const landUse = canonical_attributes.land_use || '—'
  const address = canonical_attributes.address || '—'
  const geomType = canonical_attributes.geometry_type || 'Polygon'

  const filteredConflicts = conflictsList.filter((c: AttributeConflict) => {
    if (conflictFilter === 'UNRESOLVED') return c.status === 'UNRESOLVED'
    if (conflictFilter === 'RESOLVED') return c.status === 'RESOLVED'
    if (conflictFilter === 'DISMISSED') return c.status === 'DISMISSED'
    return true
  })

  const getStatusBadge = (st: UnifiedRecordStatus) => {
    switch (st) {
      case 'ACTIVE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-950 text-emerald-300 border border-emerald-500 shadow-sm">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            Active
          </span>
        )
      case 'CONFLICT':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-red-950 text-red-300 border border-red-500 shadow-sm">
            <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
            Conflict
          </span>
        )
      case 'INCOMPLETE':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-950 text-amber-300 border border-amber-500 shadow-sm">
            <HelpCircle className="w-3.5 h-3.5 text-amber-400" />
            Incomplete
          </span>
        )
    }
  }

  const getRoleIcon = (role: string) => {
    switch (role?.toUpperCase()) {
      case 'CADASTRAL':
        return <Scale className="w-3.5 h-3.5 text-cyan-400" />
      case 'DRONE':
        return <Plane className="w-3.5 h-3.5 text-amber-400" />
      case 'MUNICIPAL':
        return <Building className="w-3.5 h-3.5 text-indigo-400" />
      default:
        return <Layers className="w-3.5 h-3.5 text-slate-400" />
    }
  }

  return (
    <>
      <div className="w-96 lg:w-[480px] bg-surface-900 border-l border-border flex flex-col h-full font-mono text-xs overflow-hidden select-none flex-shrink-0">
        {/* Header */}
        <div className="p-3.5 border-b border-border bg-surface-950/80 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span className="font-bold text-slate-200 uppercase tracking-wider text-xs">
              Unified Land Record
            </span>
          </div>
          <div className="flex items-center gap-2">
            {/* Export Quick Actions */}
            <div className="flex items-center gap-1 bg-surface-900 p-0.5 rounded border border-border">
              <button
                onClick={() => handleExportSingle('geojson')}
                disabled={Boolean(exportingType)}
                title="Export this record as GeoJSON"
                className="px-2 py-1 rounded text-[10px] font-bold text-emerald-400 hover:bg-emerald-950/60 hover:text-emerald-300 transition-colors flex items-center gap-1 disabled:opacity-50"
              >
                <FileCode className="w-3 h-3" />
                <span>GeoJSON</span>
              </button>
              <button
                onClick={() => handleExportSingle('csv')}
                disabled={Boolean(exportingType)}
                title="Export this record as CSV"
                className="px-2 py-1 rounded text-[10px] font-bold text-cyan-400 hover:bg-cyan-950/60 hover:text-cyan-300 transition-colors flex items-center gap-1 disabled:opacity-50"
              >
                <FileSpreadsheet className="w-3 h-3" />
                <span>CSV</span>
              </button>
            </div>

            {/* AI Assistant Quick Action */}
            <button
              onClick={() => openAssistantWithRecord(record.id)}
              title="Investigate this record with LandSync Evidence Assistant"
              className="px-2 py-1 rounded text-[10px] font-bold text-cyan-300 bg-cyan-950/80 border border-cyan-800 hover:bg-cyan-900 hover:text-cyan-200 transition-colors flex items-center gap-1"
            >
              <Sparkles className="w-3 h-3 text-cyan-400" />
              <span>Ask AI</span>
            </button>

            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-surface-800 text-slate-400 hover:text-slate-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-border bg-surface-950 flex-shrink-0">
          <button
            onClick={() => setActiveTab('OVERVIEW')}
            className={`flex-1 py-2 text-center text-[11px] font-bold uppercase tracking-wider transition-colors border-b-2 flex items-center justify-center gap-1.5 ${
              activeTab === 'OVERVIEW'
                ? 'border-emerald-400 text-emerald-300 bg-emerald-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Overview</span>
          </button>
          <button
            onClick={() => setActiveTab('CONFLICTS')}
            className={`flex-1 py-2 text-center text-[11px] font-bold uppercase tracking-wider transition-colors border-b-2 flex items-center justify-center gap-1.5 ${
              activeTab === 'CONFLICTS'
                ? 'border-amber-400 text-amber-300 bg-amber-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Conflicts</span>
            {totalConflicts > 0 && (
              <span
                className={`px-1.5 py-0.2 rounded-full text-[9px] font-mono font-bold ${
                  unresolvedCount > 0
                    ? 'bg-red-950 text-red-300 border border-red-700 animate-pulse'
                    : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                }`}
              >
                {unresolvedCount > 0 ? unresolvedCount : totalConflicts}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('PROVENANCE')}
            className={`flex-1 py-2 text-center text-[11px] font-bold uppercase tracking-wider transition-colors border-b-2 flex items-center justify-center gap-1.5 ${
              activeTab === 'PROVENANCE'
                ? 'border-cyan-400 text-cyan-300 bg-cyan-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>Provenance</span>
            {provenance && (
              <span className="px-1.5 py-0.2 rounded-full text-[9px] bg-cyan-950 text-cyan-400 border border-cyan-800 font-mono">
                {provenance.timeline.length}
              </span>
            )}
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Record Summary Banner */}
          <div className="p-3.5 rounded-lg bg-surface-950 border border-border shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block font-bold mb-1">
                Record Identifier
              </span>
              <div className="text-xl font-black font-mono tracking-tight text-emerald-400">
                {record_identifier}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                Harmonized from {sources.length} sources
              </div>
            </div>
            <div className="text-right">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block font-bold mb-1">
                Status
              </span>
              {getStatusBadge(status)}
            </div>
          </div>

          {activeTab === 'OVERVIEW' && (
            <>
              {/* Conflict Action Banner if Unresolved Conflicts Exist */}
              {unresolvedCount > 0 && (
                <div className="rounded-lg bg-red-950/70 border border-red-800 p-3 space-y-2.5">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-1.5 font-bold text-red-300 text-[11px]">
                      <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                      <span>{unresolvedCount} Attribute Conflict(s) Require Human Review</span>
                    </div>
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-bold uppercase bg-red-900 text-red-100">
                      Gated
                    </span>
                  </div>
                  <p className="text-[10px] text-red-200/90 leading-relaxed">
                    Contributing datasets provide conflicting values for primary attributes. This record cannot be marked active until material conflicts are reconciled.
                  </p>
                  <button
                    onClick={() => setActiveTab('CONFLICTS')}
                    className="w-full py-1.5 rounded bg-red-600 hover:bg-red-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 shadow transition-colors"
                  >
                    <span>Reconcile Attribute Conflicts</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Canonical Geometry & Spatial Metric Card */}
              <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-cyan-400" />
                    Canonical Spatial Representation
                  </span>
                  <span className="text-[10px] text-emerald-400 font-mono font-bold">
                    {geometry_source_role || 'DEFAULT'}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="p-2 rounded bg-surface-900 border border-border/80">
                    <span className="text-[9px] text-slate-500 uppercase block font-semibold">
                      Canonical Area
                    </span>
                    <span className="font-bold text-slate-200 text-sm font-mono">
                      {area !== null && area !== undefined ? `${area.toLocaleString()} m²` : '—'}
                    </span>
                  </div>

                  <div className="p-2 rounded bg-surface-900 border border-border/80">
                    <span className="text-[9px] text-slate-500 uppercase block font-semibold">
                      Geometry Type
                    </span>
                    <span className="font-bold text-slate-200 text-sm font-mono">{geomType}</span>
                  </div>
                </div>
              </div>

              {/* Canonical Attributes Table */}
              <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-2.5">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  Canonical Attributes
                </span>

                <div className="bg-surface-900 rounded border border-border/80 divide-y divide-border/40 text-[11px]">
                  <div className="p-2 flex items-center justify-between">
                    <span className="text-slate-400">Land Use / Zoning</span>
                    <span className="font-bold text-slate-200">{landUse}</span>
                  </div>
                  <div className="p-2 flex items-center justify-between">
                    <span className="text-slate-400">Locality / Address</span>
                    <span className="font-bold text-slate-200 truncate max-w-[200px]" title={address}>
                      {address}
                    </span>
                  </div>
                  <div className="p-2 flex items-center justify-between">
                    <span className="text-slate-400">Contributing Sources</span>
                    <span className="font-mono text-cyan-300 font-bold">{sources.length}</span>
                  </div>
                  <div className="p-2 flex items-center justify-between">
                    <span className="text-slate-400">Attribute Conflicts</span>
                    <span
                      className={`font-mono font-bold ${
                        unresolvedCount > 0 ? 'text-red-400' : 'text-emerald-400'
                      }`}
                    >
                      {unresolvedCount > 0
                        ? `${unresolvedCount} Unresolved (${totalConflicts} Total)`
                        : `${totalConflicts} Detected / Resolved`}
                    </span>
                  </div>
                </div>
              </div>

              {/* Contributing Source Features List */}
              <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                    Contributing Source Features ({sources.length})
                  </span>
                  <span className="text-[9px] text-slate-500 font-mono">Immutable Origin</span>
                </div>

                <div className="space-y-2">
                  {sources.map((src) => (
                    <div
                      key={src.id}
                      className="p-2.5 rounded bg-surface-900 border border-border/80 space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 font-bold text-slate-200">
                          {getRoleIcon(src.source_role)}
                          <span className="text-cyan-300">{src.source_identifier}</span>
                        </div>
                        <span className="px-1.5 py-0.2 rounded text-[9px] font-bold uppercase tracking-wider bg-surface-800 text-slate-300 border border-border">
                          {src.source_role}
                        </span>
                      </div>

                      <div className="text-[10px] text-slate-400 flex items-center justify-between">
                        <span>{src.dataset_name}</span>
                        <span className="font-mono">{src.geometry_type}</span>
                      </div>

                      {/* Inspectable source properties */}
                      {src.properties && Object.keys(src.properties).length > 0 && (
                        <div className="pt-1 border-t border-border/40 grid grid-cols-2 gap-1 text-[9px]">
                          {Object.entries(src.properties).slice(0, 4).map(([k, v]) => {
                            if (k.startsWith('_')) return null
                            return (
                              <div key={k} className="truncate">
                                <span className="text-slate-500">{k}: </span>
                                <span className="text-slate-300 font-mono">{String(v)}</span>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {activeTab === 'CONFLICTS' && (
            <div className="space-y-3.5">
              {/* Conflicts Filter Header */}
              <div className="flex items-center justify-between border-b border-border/60 pb-2">
                <div className="flex items-center gap-1.5 text-[10px]">
                  <button
                    onClick={() => setConflictFilter('ALL')}
                    className={`px-2 py-0.5 rounded font-bold transition-colors ${
                      conflictFilter === 'ALL'
                        ? 'bg-surface-800 text-slate-100 border border-slate-600'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    All ({totalConflicts})
                  </button>
                  <button
                    onClick={() => setConflictFilter('UNRESOLVED')}
                    className={`px-2 py-0.5 rounded font-bold transition-colors ${
                      conflictFilter === 'UNRESOLVED'
                        ? 'bg-red-950 text-red-200 border border-red-700'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Unresolved ({unresolvedCount})
                  </button>
                  <button
                    onClick={() => setConflictFilter('RESOLVED')}
                    className={`px-2 py-0.5 rounded font-bold transition-colors ${
                      conflictFilter === 'RESOLVED'
                        ? 'bg-emerald-950 text-emerald-200 border border-emerald-700'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Resolved ({resolvedCount})
                  </button>
                  <button
                    onClick={() => setConflictFilter('DISMISSED')}
                    className={`px-2 py-0.5 rounded font-bold transition-colors ${
                      conflictFilter === 'DISMISSED'
                        ? 'bg-slate-800 text-slate-300 border border-slate-600'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Dismissed ({dismissedCount})
                  </button>
                </div>
              </div>

              {conflictsLoading ? (
                <div className="p-8 text-center text-slate-400 font-mono">
                  <div className="w-5 h-5 border-2 border-amber-400 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  <span>Loading attribute conflicts...</span>
                </div>
              ) : filteredConflicts.length === 0 ? (
                <div className="p-8 text-center bg-surface-950 rounded-lg border border-border space-y-2">
                  <ShieldCheck className="w-8 h-8 text-emerald-500 mx-auto" />
                  <p className="font-bold text-slate-200 text-xs">No Conflicts Found</p>
                  <p className="text-[10px] text-slate-400">
                    {conflictFilter === 'ALL'
                      ? 'Contributing datasets are fully aligned on all canonical attributes.'
                      : `No conflicts matching filter '${conflictFilter}'.`}
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredConflicts.map((c: AttributeConflict) => (
                    <div
                      key={c.id}
                      className="p-3.5 rounded-lg bg-surface-950 border border-border/80 space-y-2.5"
                    >
                      {/* Conflict Header */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-100 text-xs font-mono uppercase tracking-wide">
                            {c.attribute_name}
                          </span>
                          <span
                            className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase tracking-wider ${
                              c.severity === 'HIGH'
                                ? 'bg-red-950 text-red-300 border border-red-700'
                                : c.severity === 'MEDIUM'
                                ? 'bg-amber-950 text-amber-300 border border-amber-700'
                                : 'bg-blue-950 text-blue-300 border border-blue-700'
                            }`}
                          >
                            {c.severity}
                          </span>
                        </div>

                        {/* Status Badge */}
                        {c.status === 'RESOLVED' ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-950 text-emerald-300 border border-emerald-700">
                            <Check className="w-3 h-3 text-emerald-400" />
                            Resolved
                          </span>
                        ) : c.status === 'DISMISSED' ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-surface-800 text-slate-400 border border-slate-700">
                            <Ban className="w-3 h-3" />
                            Dismissed
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-red-950 text-red-300 border border-red-700 animate-pulse">
                            <AlertTriangle className="w-3 h-3 text-red-400" />
                            Unresolved
                          </span>
                        )}
                      </div>

                      {/* Conflict Type Tag */}
                      <div className="text-[10px] text-slate-400">
                        Type: <span className="font-mono text-slate-300">{c.conflict_type.replace(/_/g, ' ')}</span>
                      </div>

                      {/* Evidence Comparison Grid */}
                      <div className="space-y-1.5 pt-1 border-t border-border/40">
                        <span className="text-[9px] text-slate-500 uppercase font-bold block">
                          Cross-Dataset Evidence ({c.detected_values.length} sources)
                        </span>

                        <div className="grid grid-cols-1 gap-1.5">
                          {c.detected_values.map((dv: ConflictSourceValue, idx: number) => (
                            <div
                              key={idx}
                              className="p-2 rounded bg-surface-900 border border-border/60 flex items-center justify-between text-[10px]"
                            >
                              <div className="flex items-center gap-2">
                                {getRoleIcon(dv.source_role)}
                                <div>
                                  <span className="font-bold text-slate-200 mr-1.5">
                                    {dv.source_role}
                                  </span>
                                  <span className="text-[9px] text-slate-400">
                                    ({dv.dataset_name})
                                  </span>
                                </div>
                              </div>

                              <span className="font-mono font-bold text-amber-300 bg-surface-950 px-2 py-0.5 rounded border border-border/40">
                                {dv.value !== null && dv.value !== undefined ? String(dv.value) : 'NULL'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Resolved Details Box */}
                      {c.status === 'RESOLVED' && c.resolution && (
                        <div className="p-2.5 rounded bg-emerald-950/40 border border-emerald-800/80 space-y-1 text-[10px]">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-emerald-300 uppercase tracking-wide flex items-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                              Canonical Value: {String(c.resolution.resolved_value)}
                            </span>
                            <span className="text-[9px] text-slate-400 font-mono">
                              via {c.resolution.resolution_type}
                            </span>
                          </div>
                          {c.resolution.comment && (
                            <p className="text-slate-300 italic text-[10px]">
                              "{c.resolution.comment}"
                            </p>
                          )}
                          <div className="text-[9px] text-slate-500 flex items-center justify-between pt-0.5">
                            <span>By: {c.resolution.resolved_by || 'GIS Reviewer'}</span>
                            <span>{formatDate(c.resolution.resolved_at)}</span>
                          </div>
                        </div>
                      )}

                      {/* Dismissed Details Box */}
                      {c.status === 'DISMISSED' && (
                        <div className="p-2.5 rounded bg-surface-900 border border-border space-y-1 text-[10px]">
                          <div className="flex items-center gap-1 font-bold text-slate-300 uppercase tracking-wide">
                            <Ban className="w-3.5 h-3.5 text-slate-400" />
                            Dismissed (Variance Accepted)
                          </div>
                          {c.dismissal_reason && (
                            <p className="text-slate-300 italic text-[10px]">
                              "{c.dismissal_reason}"
                            </p>
                          )}
                          <div className="text-[9px] text-slate-500 flex items-center justify-between pt-0.5">
                            <span>Status: Inactive Conflict</span>
                            <span>{formatDate(c.updated_at)}</span>
                          </div>
                        </div>
                      )}

                      {/* Action Button */}
                      <div className="pt-1.5 flex items-center justify-end gap-2">
                        <button
                          onClick={() => openAssistantWithConflict(c.id)}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-800 text-cyan-300 hover:text-cyan-100 text-xs transition-colors"
                          title="Explain this discrepancy and cross-dataset evidence with AI"
                        >
                          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                          <span>Explain with AI</span>
                        </button>

                        {c.status === 'UNRESOLVED' ? (
                          <button
                            onClick={() => openResolutionModal(c)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-surface-950 font-bold text-xs shadow-sm transition-all active:scale-[0.98]"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Reconcile Conflict</span>
                          </button>
                        ) : (
                          <button
                            onClick={() => openResolutionModal(c)}
                            className="px-2.5 py-1 rounded bg-surface-900 hover:bg-surface-850 text-slate-400 hover:text-slate-200 border border-border text-[10px] transition-colors"
                          >
                            Change Resolution
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'PROVENANCE' && (
            /* PROVENANCE TAB */
            <div className="space-y-4">
              {provLoading ? (
                <div className="p-8 text-center text-slate-400 font-mono">
                  <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  <span>Tracing provenance chain...</span>
                </div>
              ) : provenance ? (
                <>
                  {/* Contributing Sources Lineage Card */}
                  <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <Database className="w-3.5 h-3.5 text-cyan-400" />
                        Source Provenance ({provenance.sources.length})
                      </span>
                      <span className="text-[9px] text-slate-500 font-mono">Real Evidence</span>
                    </div>

                    <div className="space-y-2">
                      {provenance.sources.map((s) => (
                        <div
                          key={s.feature_id}
                          className="p-2.5 rounded bg-surface-900 border border-border/80 space-y-1.5"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              {getRoleIcon(s.role)}
                              <span className="font-bold text-slate-200 text-xs text-cyan-300">
                                {s.feature_identifier}
                              </span>
                            </div>
                            <span className="px-1.5 py-0.2 rounded text-[9px] font-bold uppercase tracking-wider bg-surface-800 text-slate-300 border border-border">
                              {s.role}
                            </span>
                          </div>

                          <div className="text-[10px] text-slate-400 flex items-center justify-between">
                            <span>
                              {s.dataset_name} <span className="text-slate-500 font-mono">v{s.dataset_version || 1}</span>
                            </span>
                            <span className="font-mono text-slate-500">{s.dataset_format || 'GeoJSON'}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Match Evidence Card */}
                  <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-2.5">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                      Machine Match Evidence
                    </span>

                    {provenance.relationships.length > 0 ? (
                      <div className="space-y-2">
                        {provenance.relationships.map((rel) => (
                          <div
                            key={rel.match_id}
                            className="p-2.5 rounded bg-surface-900 border border-border/80 space-y-2 text-[11px]"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-emerald-400 font-mono">
                                {(rel.machine_score * 100).toFixed(1)}% Match
                              </span>
                              <span className="px-2 py-0.5 rounded-full text-[9px] font-bold uppercase bg-emerald-950 text-emerald-300 border border-emerald-600">
                                {rel.human_decision}
                              </span>
                            </div>

                            <div className="grid grid-cols-2 gap-2 text-[10px]">
                              <div className="p-1.5 rounded bg-surface-950 border border-border/50">
                                <span className="text-slate-500 block">Candidate Rank</span>
                                <span className="font-bold text-slate-200">
                                  {rel.candidate_rank ? `#${rel.candidate_rank}` : '#1'} {rel.is_best_candidate && '(Best)'}
                                </span>
                              </div>
                              <div className="p-1.5 rounded bg-surface-950 border border-border/50">
                                <span className="text-slate-500 block">Quality Tier</span>
                                <span className="font-bold text-cyan-300">{rel.match_tier || 'HIGH'}</span>
                              </div>
                            </div>

                            {/* Reasons/Signals summary if present */}
                            {rel.reasons && Object.keys(rel.reasons).length > 0 && (
                              <div className="pt-1 border-t border-border/40 text-[9px] space-y-1">
                                <span className="text-slate-500 uppercase font-bold block">Match Signals</span>
                                <div className="grid grid-cols-2 gap-1 text-slate-400">
                                  {Object.entries(rel.reasons).slice(0, 4).map(([k, v]) => (
                                    <div key={k} className="truncate">
                                      <span>{k.replace(/_/g, ' ')}: </span>
                                      <span className="text-slate-200 font-mono font-bold">{String(v)}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-3 text-center text-slate-500 text-[10px]">
                        No direct matching evidence recorded.
                      </div>
                    )}
                  </div>

                  {/* Review Audit History */}
                  <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-2.5">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                      <Award className="w-3.5 h-3.5 text-violet-400" />
                      Human Review Decisions ({provenance.review_history.length})
                    </span>

                    {provenance.review_history.length > 0 ? (
                      <div className="space-y-1.5">
                        {provenance.review_history.map((rev) => (
                          <div
                            key={rev.id}
                            className="p-2 rounded bg-surface-900 border border-border/70 text-[10px] space-y-1"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-emerald-300 uppercase tracking-wider">
                                {rev.decision}
                              </span>
                              <span className="text-slate-500 font-mono text-[9px]">
                                {formatDate(rev.created_at)}
                              </span>
                            </div>
                            {rev.comment && (
                              <p className="text-slate-300 italic text-[10px]">"{rev.comment}"</p>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-3 text-center text-slate-500 text-[10px]">
                        No review decisions logged.
                      </div>
                    )}
                  </div>

                  {/* Chronological Provenance Timeline */}
                  <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-emerald-400" />
                        Chronological Provenance Timeline
                      </span>
                      <span className="text-[9px] text-slate-500 font-mono">
                        {provenance.timeline.length} events
                      </span>
                    </div>

                    <div className="relative pl-4 space-y-3 before:absolute before:left-1.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-border/80">
                      {provenance.timeline.map((event, idx) => (
                        <div key={idx} className="relative group">
                          {/* Dot */}
                          <div className="absolute -left-4 top-1 w-2.5 h-2.5 rounded-full bg-surface-900 border-2 border-emerald-400 group-hover:scale-125 transition-transform" />

                          <div className="p-2 rounded bg-surface-900 border border-border/70 space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-200 text-[10px]">
                                {event.title}
                              </span>
                              <span className="text-[9px] text-slate-500 font-mono">
                                {formatDate(event.timestamp)}
                              </span>
                            </div>
                            <p className="text-[9px] text-slate-400 leading-relaxed">
                              {event.description}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <div className="p-6 text-center text-slate-500 text-xs">
                  Provenance data unavailable.
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Resolution Modal */}
      <ConflictResolutionModal
        conflict={selectedConflictForModal}
        projectId={record.project_id}
        recordId={record.id}
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false)
          setSelectedConflictForModal(null)
        }}
      />
    </>
  )
}
