import React from 'react'
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
} from 'lucide-react'
import type { UnifiedRecordDetail, UnifiedRecordStatus, SourceRole } from '../../types'

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
  if (isLoading) {
    return (
      <div className="w-96 lg:w-[420px] bg-surface-900 border-l border-border flex flex-col items-center justify-center p-8 text-slate-400 font-mono text-xs flex-shrink-0">
        <div className="w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin mb-3" />
        <span>Loading unified land record...</span>
      </div>
    )
  }

  if (!record) {
    return (
      <div className="w-96 lg:w-[420px] bg-surface-900 border-l border-border flex flex-col items-center justify-center p-8 text-center text-slate-500 font-mono text-xs select-none flex-shrink-0">
        <ShieldCheck className="w-8 h-8 text-slate-600 mb-3" />
        <p className="font-semibold text-slate-400 mb-1">No Record Selected</p>
        <p className="text-[11px] leading-relaxed">
          Select a unified land record from the table to inspect its canonical aggregation, contributing source features, and attribute conflict analysis.
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
    created_at,
    updated_at,
  } = record

  const conflicts = canonical_attributes.conflicts || []
  const landUse = canonical_attributes.land_use || '—'
  const address = canonical_attributes.address || '—'
  const geomType = canonical_attributes.geometry_type || 'Polygon'

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

  const getRoleIcon = (role: SourceRole) => {
    switch (role) {
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
    <div className="w-96 lg:w-[420px] bg-surface-900 border-l border-border flex flex-col h-full font-mono text-xs overflow-hidden select-none flex-shrink-0">
      {/* Header */}
      <div className="p-3.5 border-b border-border bg-surface-950/80 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span className="font-bold text-slate-200 uppercase tracking-wider text-xs">
            Unified Land Record
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-surface-800 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <X className="w-4 h-4" />
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

        {/* Conflict Warning Alert if CONFLICT status */}
        {status === 'CONFLICT' && conflicts.length > 0 && (
          <div className="rounded-lg bg-red-950/70 border border-red-800 p-3 space-y-2">
            <div className="flex items-start gap-1.5 font-bold text-red-300 text-[11px]">
              <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <span>Attribute Disagreement Detected</span>
            </div>
            <p className="text-[10px] text-red-200/90 leading-relaxed">
              Contributing datasets provide conflicting canonical attributes for this property parcel. Differences are highlighted below.
            </p>
            <div className="space-y-1.5 pt-1">
              {conflicts.map((conf: any, idx: number) => (
                <div key={idx} className="p-2 rounded bg-surface-950 border border-red-900/60 text-[10px]">
                  <div className="flex items-center justify-between text-red-300 font-bold uppercase mb-1">
                    <span>{conf.field}</span>
                    <span className="text-[9px] text-slate-400">{conf.type}</span>
                  </div>
                  <div className="space-y-0.5">
                    {conf.values &&
                      Object.entries(conf.values).map(([role, val]) => (
                        <div key={role} className="flex justify-between text-slate-300">
                          <span className="text-slate-400">{role}:</span>
                          <span className="font-bold text-amber-300">{String(val)}</span>
                        </div>
                      ))}
                  </div>
                </div>
              ))}
            </div>
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
      </div>
    </div>
  )
}
