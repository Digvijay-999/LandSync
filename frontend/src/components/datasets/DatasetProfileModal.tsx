import React, { useState } from 'react'
import {
  X,
  Layers,
  Database,
  Globe,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Table,
  Hash,
  ShieldCheck,
  Calendar,
  HardDrive,
} from 'lucide-react'
import type { Dataset } from '../../types'
import { formatBytes, formatDate } from '../../lib/utils'

interface DatasetProfileModalProps {
  dataset: Dataset | null
  isOpen: boolean
  onClose: () => void
}

export const DatasetProfileModal: React.FC<DatasetProfileModalProps> = ({
  dataset,
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'spatial' | 'attributes' | 'quality'>('overview')

  if (!isOpen || !dataset) return null

  const profile = dataset.profile
  const validityPct = profile?.geometry?.validity_percentage ?? 100

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-4xl bg-surface-900 border border-border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface-950/70">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cyan-950/80 border border-cyan-800 text-cyan-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold font-mono text-slate-100">
                  {dataset.name}
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded uppercase font-semibold bg-surface-800 border border-border text-cyan-400">
                  {dataset.source_format}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded uppercase font-semibold bg-emerald-950 border border-emerald-800 text-emerald-400">
                  {dataset.status}
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                {dataset.source_filename} • {formatBytes(dataset.file_size)}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-surface-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 px-6 pt-3 border-b border-border bg-surface-950/30 text-xs font-mono">
          <button
            onClick={() => setActiveTab('overview')}
            className={`pb-2.5 px-3 border-b-2 font-medium transition-colors ${
              activeTab === 'overview'
                ? 'border-cyan-400 text-cyan-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Overview & Geometry
          </button>
          <button
            onClick={() => setActiveTab('spatial')}
            className={`pb-2.5 px-3 border-b-2 font-medium transition-colors ${
              activeTab === 'spatial'
                ? 'border-cyan-400 text-cyan-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Spatial Extent & CRS
          </button>
          <button
            onClick={() => setActiveTab('attributes')}
            className={`pb-2.5 px-3 border-b-2 font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === 'attributes'
                ? 'border-cyan-400 text-cyan-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>Attributes Schema</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-surface-800 text-slate-300">
              {profile?.attributes?.field_count ?? 0}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('quality')}
            className={`pb-2.5 px-3 border-b-2 font-medium transition-colors ${
              activeTab === 'quality'
                ? 'border-cyan-400 text-cyan-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Data Quality Audit
          </button>
        </div>

        {/* Body Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* OVERVIEW TAB */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Stat Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-3.5 rounded-lg bg-surface-950 border border-border">
                  <div className="text-[11px] font-mono text-slate-400 mb-1">Feature Count</div>
                  <div className="text-xl font-bold font-mono text-slate-100">
                    {dataset.feature_count.toLocaleString()}
                  </div>
                </div>

                <div className="p-3.5 rounded-lg bg-surface-950 border border-border">
                  <div className="text-[11px] font-mono text-slate-400 mb-1">Primary Geometry</div>
                  <div className="text-xl font-bold font-mono text-cyan-400 truncate">
                    {dataset.geometry_type}
                  </div>
                </div>

                <div className="p-3.5 rounded-lg bg-surface-950 border border-border">
                  <div className="text-[11px] font-mono text-slate-400 mb-1">Validity Rate</div>
                  <div className="text-xl font-bold font-mono text-emerald-400">
                    {validityPct}%
                  </div>
                </div>

                <div className="p-3.5 rounded-lg bg-surface-950 border border-border">
                  <div className="text-[11px] font-mono text-slate-400 mb-1">Source CRS</div>
                  <div className="text-xl font-bold font-mono text-slate-100 truncate">
                    {dataset.detected_crs || 'N/A'}
                  </div>
                </div>
              </div>

              {/* Geometry Distribution */}
              {profile?.geometry && (
                <div className="p-4 rounded-xl bg-surface-950 border border-border space-y-3">
                  <h3 className="text-xs font-mono font-semibold text-slate-300 tracking-wider uppercase flex items-center gap-2">
                    <Database className="w-4 h-4 text-cyan-400" />
                    <span>Geometry Distribution</span>
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(profile.geometry.geometry_type_distribution).map(
                      ([type, count]) => (
                        <div
                          key={type}
                          className="px-3 py-1.5 rounded-lg bg-surface-900 border border-border flex items-center gap-2 text-xs font-mono"
                        >
                          <span className="text-slate-300">{type}</span>
                          <span className="px-1.5 py-0.5 rounded bg-surface-950 text-cyan-400 font-semibold">
                            {count}
                          </span>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}

              {/* Version & Storage */}
              <div className="p-4 rounded-xl bg-surface-950 border border-border space-y-3">
                <h3 className="text-xs font-mono font-semibold text-slate-300 tracking-wider uppercase flex items-center gap-2">
                  <HardDrive className="w-4 h-4 text-cyan-400" />
                  <span>Version & Storage Provenance</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
                  <div className="space-y-1">
                    <div className="text-slate-400 text-[11px]">Dataset ID</div>
                    <div className="text-slate-200 truncate select-all">{dataset.id}</div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-slate-400 text-[11px]">Ingestion Timestamp</div>
                    <div className="text-slate-200">{formatDate(dataset.created_at)}</div>
                  </div>
                  {dataset.versions && dataset.versions[0]?.checksum && (
                    <div className="sm:col-span-2 space-y-1">
                      <div className="text-slate-400 text-[11px]">SHA-256 Checksum</div>
                      <div className="text-slate-300 font-mono text-[11px] bg-surface-900 p-2 rounded border border-border break-all select-all">
                        {dataset.versions[0].checksum}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* SPATIAL TAB */}
          {activeTab === 'spatial' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-surface-950 border border-border space-y-2">
                  <div className="text-[11px] font-mono text-slate-400">CRS Identifier</div>
                  <div className="text-base font-bold font-mono text-cyan-400">
                    {dataset.detected_crs || 'Unspecified'}
                  </div>
                  <div className="text-xs text-slate-400 font-mono">
                    {profile?.spatial?.crs_name || 'Standard Coordinate Reference System'}
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-surface-950 border border-border space-y-2">
                  <div className="text-[11px] font-mono text-slate-400">Coordinate Type</div>
                  <div className="text-base font-bold font-mono text-slate-200">
                    {profile?.spatial?.is_geographic ? 'Geographic (Lat / Lon)' : 'Projected'}
                  </div>
                  <div className="text-xs text-slate-400 font-mono">
                    Ellipsoidal degrees or projected metric units
                  </div>
                </div>
              </div>

              {/* Bounding Box Visualizer Box */}
              {dataset.bounding_box && (
                <div className="p-5 rounded-xl bg-surface-950 border border-border space-y-4">
                  <h3 className="text-xs font-mono font-semibold text-slate-300 tracking-wider uppercase flex items-center gap-2">
                    <Globe className="w-4 h-4 text-cyan-400" />
                    <span>Spatial Bounding Box (Extent)</span>
                  </h3>

                  <div className="max-w-md mx-auto p-4 rounded-xl bg-surface-900 border border-border/80 text-center font-mono text-xs space-y-3">
                    {/* North (Max Y) */}
                    <div>
                      <span className="text-[10px] text-slate-400 block uppercase">Max Latitude (Y)</span>
                      <span className="text-slate-100 font-semibold">{dataset.bounding_box.max_y}</span>
                    </div>

                    <div className="flex items-center justify-between px-2">
                      {/* West (Min X) */}
                      <div className="text-left">
                        <span className="text-[10px] text-slate-400 block uppercase">Min Longitude (X)</span>
                        <span className="text-slate-100 font-semibold">{dataset.bounding_box.min_x}</span>
                      </div>

                      <div className="w-16 h-12 rounded border border-cyan-800/80 bg-cyan-950/30 flex items-center justify-center text-[10px] text-cyan-400">
                        BBOX
                      </div>

                      {/* East (Max X) */}
                      <div className="text-right">
                        <span className="text-[10px] text-slate-400 block uppercase">Max Longitude (X)</span>
                        <span className="text-slate-100 font-semibold">{dataset.bounding_box.max_x}</span>
                      </div>
                    </div>

                    {/* South (Min Y) */}
                    <div>
                      <span className="text-[10px] text-slate-400 block uppercase">Min Latitude (Y)</span>
                      <span className="text-slate-100 font-semibold">{dataset.bounding_box.min_y}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ATTRIBUTES TAB */}
          {activeTab === 'attributes' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                <span>Total Columns: {profile?.attributes?.fields.length ?? 0}</span>
                <span>(Excluding primary geometry column)</span>
              </div>

              <div className="rounded-xl border border-border overflow-hidden bg-surface-950">
                <table className="w-full text-left font-mono text-xs">
                  <thead className="bg-surface-900 border-b border-border text-[11px] text-slate-400">
                    <tr>
                      <th className="py-2.5 px-4 font-semibold">Field Name</th>
                      <th className="py-2.5 px-4 font-semibold">Data Type</th>
                      <th className="py-2.5 px-4 font-semibold">Null Count</th>
                      <th className="py-2.5 px-4 font-semibold">Unique Values</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {profile?.attributes?.fields && profile.attributes.fields.length > 0 ? (
                      profile.attributes.fields.map((field) => (
                        <tr key={field.name} className="hover:bg-surface-900/60 transition-colors">
                          <td className="py-2 px-4 font-medium text-slate-200">
                            {field.name}
                          </td>
                          <td className="py-2 px-4 text-cyan-400">
                            {field.data_type}
                          </td>
                          <td className="py-2 px-4">
                            {field.null_count > 0 ? (
                              <span className="text-amber-400 font-semibold">
                                {field.null_count}
                              </span>
                            ) : (
                              <span className="text-slate-500">0</span>
                            )}
                          </td>
                          <td className="py-2 px-4 text-slate-300">
                            {field.unique_count}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={4} className="py-6 text-center text-slate-400">
                          No non-spatial attribute fields found in dataset.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* QUALITY TAB */}
          {activeTab === 'quality' && (
            <div className="space-y-6">
              {/* Validity Overview Card */}
              <div className="p-5 rounded-xl bg-surface-950 border border-border space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-mono font-semibold text-slate-300 tracking-wider uppercase flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <span>Geometry Validity Metric</span>
                  </h3>
                  <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                    validityPct === 100
                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                      : 'bg-rose-950 text-rose-300 border border-rose-800'
                  }`}>
                    {validityPct}% OGC Compliant
                  </span>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-surface-850 h-2.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      validityPct === 100 ? 'bg-emerald-500' : 'bg-rose-500'
                    }`}
                    style={{ width: `${validityPct}%` }}
                  />
                </div>

                <div className="grid grid-cols-3 gap-3 pt-2 text-center font-mono text-xs">
                  <div className="p-3 rounded-lg bg-surface-900 border border-border">
                    <span className="text-slate-400 text-[10px] uppercase block">Valid Geometries</span>
                    <span className="text-emerald-400 font-bold text-base">
                      {profile?.geometry?.valid_geometry_count ?? 0}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-surface-900 border border-border">
                    <span className="text-slate-400 text-[10px] uppercase block">Invalid Geometries</span>
                    <span className={`font-bold text-base ${
                      (profile?.geometry?.invalid_geometry_count ?? 0) > 0 ? 'text-rose-400' : 'text-slate-500'
                    }`}>
                      {profile?.geometry?.invalid_geometry_count ?? 0}
                    </span>
                  </div>
                  <div className="p-3 rounded-lg bg-surface-900 border border-border">
                    <span className="text-slate-400 text-[10px] uppercase block">Empty Geometries</span>
                    <span className="text-slate-400 font-bold text-base">
                      {profile?.geometry?.empty_geometry_count ?? 0}
                    </span>
                  </div>
                </div>
              </div>

              {/* Quality Note */}
              <div className="p-4 rounded-xl bg-surface-950 border border-border text-xs text-slate-400 font-mono leading-relaxed">
                <span className="font-semibold text-slate-300 block mb-1">Architecture Note:</span>
                Source geometries are strictly preserved in their original state during Milestone 1 ingestion. Invalid geometries (e.g. self-intersections or unclosed rings) are detected and flagged without automatic destructive repair. Advanced geometric cleaning will execute during the downstream Harmonization & Validation stage.
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-3.5 border-t border-border bg-surface-950/70">
          <div className="text-[11px] font-mono text-slate-400">
            LandSync AI Vector Profiler • Ready for CRS & Schema Normalization
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-slate-200 text-xs font-mono font-medium transition-colors"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  )
}
