import React, { useState } from 'react'
import {
  Compass,
  Crosshair,
  Layers,
  CircleDot,
  GitCompare,
  Flame,
  BarChart3,
  Loader2,
  Sparkles,
  MapPin,
  CheckCircle2,
  AlertCircle,
  X,
  Play,
  RotateCcw,
  Clock,
  History,
  Download,
  FileSpreadsheet,
  FileCode2,
} from 'lucide-react'
import { useProjectDatasets } from '../../hooks/useDatasets'
import {
  useProximityAnalysis,
  useBufferAnalysis,
  useIntersectionAnalysis,
  useDatasetComparison,
  useSpatialStatistics,
  useSpatialConflictAnalysis,
  useVersionComparison,
  useAnalysisHistory,
} from '../../hooks/useSpatialAnalysis'
import { api } from '../../services/api'
import { useAppStore } from '../../stores/useAppStore'
import type { SpatialAnalysisResult } from '../../types'

interface SpatialAnalysisPanelProps {
  projectId: string
  onClose?: () => void
}

type TabType =
  | 'proximity'
  | 'buffer'
  | 'intersection'
  | 'compare'
  | 'temporal'
  | 'conflicts'
  | 'history'
  | 'statistics'

export const SpatialAnalysisPanel: React.FC<SpatialAnalysisPanelProps> = ({
  projectId,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('proximity')

  const { data: datasetsData } = useProjectDatasets(projectId)
  const datasets = datasetsData?.items || []

  // Store actions
  const {
    activeSpatialAnalysis,
    setActiveSpatialAnalysis,
    clearActiveSpatialAnalysis,
    toggleAssistant,
  } = useAppStore()

  // Proximity form state
  const [targetDatasetId, setTargetDatasetId] = useState<string>('')
  const [referenceDatasetId, setReferenceDatasetId] = useState<string>('')
  const [proxDistance, setProxDistance] = useState<number>(100)
  const [proxLat, setProxLat] = useState<number>(18.522)
  const [proxLon, setProxLon] = useState<number>(73.852)

  // Buffer form state
  const [bufferDistance, setBufferDistance] = useState<number>(50)
  const [bufferFeatureId, setBufferFeatureId] = useState<string>('')

  // Intersection form state
  const [datasetAId, setDatasetAId] = useState<string>('')
  const [datasetBId, setDatasetBId] = useState<string>('')
  const [minOverlapPct, setMinOverlapPct] = useState<number>(0)

  // Temporal version state
  const [temporalDatasetId, setTemporalDatasetId] = useState<string>('')
  const [versionResult, setVersionResult] = useState<any>(null)

  // Mutations & Queries
  const proximityMutation = useProximityAnalysis()
  const bufferMutation = useBufferAnalysis()
  const intersectionMutation = useIntersectionAnalysis()
  const comparisonMutation = useDatasetComparison()
  const conflictMutation = useSpatialConflictAnalysis()
  const versionMutation = useVersionComparison()
  const { data: statsData, isLoading: statsLoading, refetch: refetchStats } = useSpatialStatistics(projectId)
  const { data: historyData, isLoading: historyLoading } = useAnalysisHistory(projectId)

  // Set default datasets when loaded
  React.useEffect(() => {
    if (datasets.length >= 2 && !datasetAId && !datasetBId) {
      setDatasetAId(datasets[0].id)
      setDatasetBId(datasets[1].id)
      setTargetDatasetId(datasets[0].id)
      setTemporalDatasetId(datasets[0].id)
      if (datasets.length >= 3) {
        setReferenceDatasetId(datasets[2].id)
      } else {
        setReferenceDatasetId(datasets[1].id)
      }
    } else if (datasets.length === 1 && !targetDatasetId) {
      setTargetDatasetId(datasets[0].id)
      setTemporalDatasetId(datasets[0].id)
    }
  }, [datasets, datasetAId, datasetBId, targetDatasetId])

  const handleRunProximity = async () => {
    try {
      const res = await proximityMutation.mutateAsync({
        project_id: projectId,
        target_dataset_id: targetDatasetId || undefined,
        reference_dataset_id: referenceDatasetId || undefined,
        latitude: !referenceDatasetId ? proxLat : undefined,
        longitude: !referenceDatasetId ? proxLon : undefined,
        distance_meters: proxDistance,
        limit: 50,
      })
      setActiveSpatialAnalysis(res)
    } catch (e) {
      console.error(e)
    }
  }

  const handleRunBuffer = async () => {
    try {
      const res = await bufferMutation.mutateAsync({
        project_id: projectId,
        latitude: proxLat,
        longitude: proxLon,
        distance_meters: bufferDistance,
        feature_id: bufferFeatureId || undefined,
      })
      setActiveSpatialAnalysis(res)
    } catch (e) {
      console.error(e)
    }
  }

  const handleRunIntersection = async () => {
    if (!datasetAId || !datasetBId) return
    try {
      const res = await intersectionMutation.mutateAsync({
        project_id: projectId,
        dataset_a_id: datasetAId,
        dataset_b_id: datasetBId,
        min_overlap_pct: minOverlapPct,
        limit: 100,
      })
      setActiveSpatialAnalysis(res)
    } catch (e) {
      console.error(e)
    }
  }

  const handleRunComparison = async () => {
    if (!datasetAId || !datasetBId) return
    try {
      const res = await comparisonMutation.mutateAsync({
        project_id: projectId,
        dataset_a_id: datasetAId,
        dataset_b_id: datasetBId,
      })
      setActiveSpatialAnalysis(res.analysis)
    } catch (e) {
      console.error(e)
    }
  }

  const handleRunConflictClustering = async () => {
    try {
      const res = await conflictMutation.mutateAsync({
        project_id: projectId,
        limit: 50,
      })
      setActiveSpatialAnalysis(res.analysis)
    } catch (e) {
      console.error(e)
    }
  }

  const handleRunVersionComparison = async () => {
    if (!temporalDatasetId) return
    try {
      const res = await versionMutation.mutateAsync({
        project_id: projectId,
        dataset_id: temporalDatasetId,
        version_a_number: 1,
      })
      setVersionResult(res)
      if (res.analysis) {
        setActiveSpatialAnalysis(res.analysis)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleExport = async (format: 'geojson' | 'csv') => {
    if (!activeSpatialAnalysis) return
    try {
      const blob = await api.exportAnalysisResult(activeSpatialAnalysis, format)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `landsync_${activeSpatialAnalysis.analysis_type.toLowerCase()}_${format === 'csv' ? 'data.csv' : 'features.geojson'}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      console.error('Export failed', err)
    }
  }

  const handleInvestigateWithAI = (analysis: SpatialAnalysisResult) => {
    useAppStore.setState({
      assistantOpen: true,
      assistantContextRecordId: null,
      assistantContextConflictId: null,
    })
  }

  const isExecuting =
    proximityMutation.isPending ||
    bufferMutation.isPending ||
    intersectionMutation.isPending ||
    comparisonMutation.isPending ||
    conflictMutation.isPending ||
    versionMutation.isPending

  return (
    <div className="flex flex-col h-full bg-surface-900 border-l border-border text-slate-100 text-xs shadow-2xl overflow-hidden w-96">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface-950/80">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <h2 className="font-bold text-sm tracking-wide text-white">Geospatial Intelligence</h2>
            <p className="text-[10px] text-slate-400">PostGIS Vector Analysis & Intelligence</p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="grid grid-cols-4 gap-1 p-2 bg-surface-950 border-b border-border text-[10px]">
        <button
          onClick={() => setActiveTab('proximity')}
          className={`px-2 py-1.5 rounded flex items-center justify-center gap-1 font-medium transition-colors ${
            activeTab === 'proximity'
              ? 'bg-cyan-600 text-white font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-surface-800'
          }`}
          title="Proximity Search"
        >
          <Crosshair className="w-3 h-3" />
          <span>Proximity</span>
        </button>

        <button
          onClick={() => setActiveTab('intersection')}
          className={`px-2 py-1.5 rounded flex items-center justify-center gap-1 font-medium transition-colors ${
            activeTab === 'intersection'
              ? 'bg-cyan-600 text-white font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-surface-800'
          }`}
          title="Intersection & Overlap"
        >
          <Layers className="w-3 h-3" />
          <span>Intersect</span>
        </button>

        <button
          onClick={() => setActiveTab('compare')}
          className={`px-2 py-1.5 rounded flex items-center justify-center gap-1 font-medium transition-colors ${
            activeTab === 'compare'
              ? 'bg-cyan-600 text-white font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-surface-800'
          }`}
          title="Compare Datasets"
        >
          <GitCompare className="w-3 h-3" />
          <span>Compare</span>
        </button>

        <button
          onClick={() => setActiveTab('temporal')}
          className={`px-2 py-1.5 rounded flex items-center justify-center gap-1 font-medium transition-colors ${
            activeTab === 'temporal'
              ? 'bg-cyan-600 text-white font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-surface-800'
          }`}
          title="Temporal Version Comparison"
        >
          <Clock className="w-3 h-3" />
          <span>Versions</span>
        </button>

        <button
          onClick={() => setActiveTab('conflicts')}
          className={`px-2 py-1.5 rounded flex items-center justify-center gap-1 font-medium transition-colors ${
            activeTab === 'conflicts'
              ? 'bg-cyan-600 text-white font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-surface-800'
          }`}
          title="Conflict Clusters"
        >
          <Flame className="w-3 h-3" />
          <span>Hotspots</span>
        </button>

        <button
          onClick={() => setActiveTab('buffer')}
          className={`px-2 py-1.5 rounded flex items-center justify-center gap-1 font-medium transition-colors ${
            activeTab === 'buffer'
              ? 'bg-cyan-600 text-white font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-surface-800'
          }`}
          title="Buffer Radius"
        >
          <CircleDot className="w-3 h-3" />
          <span>Buffer</span>
        </button>

        <button
          onClick={() => setActiveTab('history')}
          className={`px-2 py-1.5 rounded flex items-center justify-center gap-1 font-medium transition-colors ${
            activeTab === 'history'
              ? 'bg-cyan-600 text-white font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-surface-800'
          }`}
          title="Analysis History"
        >
          <History className="w-3 h-3" />
          <span>History</span>
        </button>

        <button
          onClick={() => setActiveTab('statistics')}
          className={`px-2 py-1.5 rounded flex items-center justify-center gap-1 font-medium transition-colors ${
            activeTab === 'statistics'
              ? 'bg-cyan-600 text-white font-semibold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-surface-800'
          }`}
          title="Coverage Statistics"
        >
          <BarChart3 className="w-3 h-3" />
          <span>Stats</span>
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Tab 1: Proximity */}
        {activeTab === 'proximity' && (
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-300">Target Dataset (Features to find)</label>
              <select
                value={targetDatasetId}
                onChange={(e) => setTargetDatasetId(e.target.value)}
                className="w-full bg-surface-950 border border-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="">All Project Datasets</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.geometry_type || 'Features'})
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-300">Reference Dataset (Measure distance from)</label>
              <select
                value={referenceDatasetId}
                onChange={(e) => setReferenceDatasetId(e.target.value)}
                className="w-full bg-surface-950 border border-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value="">None (Use Center Coordinates)</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.feature_count} features)
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <div className="flex justify-between items-center text-[11px]">
                <label className="font-semibold text-slate-300">Search Radius (Meters)</label>
                <span className="font-mono text-cyan-400">{proxDistance} m</span>
              </div>
              <input
                type="range"
                min="10"
                max="1000"
                step="10"
                value={proxDistance}
                onChange={(e) => setProxDistance(Number(e.target.value))}
                className="w-full accent-cyan-500"
              />
            </div>

            {!referenceDatasetId && (
              <div className="grid grid-cols-2 gap-2 pt-1">
                <div>
                  <label className="text-[10px] text-slate-400">Center Latitude</label>
                  <input
                    type="number"
                    step="0.001"
                    value={proxLat}
                    onChange={(e) => setProxLat(Number(e.target.value))}
                    className="w-full bg-surface-950 border border-border rounded px-2 py-1 text-slate-200"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400">Center Longitude</label>
                  <input
                    type="number"
                    step="0.001"
                    value={proxLon}
                    onChange={(e) => setProxLon(Number(e.target.value))}
                    className="w-full bg-surface-950 border border-border rounded px-2 py-1 text-slate-200"
                  />
                </div>
              </div>
            )}

            <button
              onClick={handleRunProximity}
              disabled={isExecuting}
              className="w-full mt-2 py-2 rounded bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>Execute PostGIS Proximity</span>
            </button>
          </div>
        )}

        {/* Tab 2: Intersection */}
        {activeTab === 'intersection' && (
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-300">Dataset A (Primary)</label>
              <select
                value={datasetAId}
                onChange={(e) => setDatasetAId(e.target.value)}
                className="w-full bg-surface-950 border border-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.feature_count} features)
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-300">Dataset B (Intersecting Candidate)</label>
              <select
                value={datasetBId}
                onChange={(e) => setDatasetBId(e.target.value)}
                className="w-full bg-surface-950 border border-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.feature_count} features)
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <div className="flex justify-between items-center text-[11px]">
                <label className="font-semibold text-slate-300">Minimum Overlap %</label>
                <span className="font-mono text-cyan-400">{minOverlapPct}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="90"
                step="5"
                value={minOverlapPct}
                onChange={(e) => setMinOverlapPct(Number(e.target.value))}
                className="w-full accent-cyan-500"
              />
            </div>

            <button
              onClick={handleRunIntersection}
              disabled={isExecuting || !datasetAId || !datasetBId}
              className="w-full mt-2 py-2 rounded bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>Compute Intersections & Overlap</span>
            </button>
          </div>
        )}

        {/* Tab 3: Compare Datasets */}
        {activeTab === 'compare' && (
          <div className="space-y-3">
            <p className="text-[11px] text-slate-400">
              Evaluates two datasets to identify overlapping features, unmatched regions, and coverage discrepancies.
            </p>

            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-300">Dataset A (Reference)</label>
              <select
                value={datasetAId}
                onChange={(e) => setDatasetAId(e.target.value)}
                className="w-full bg-surface-950 border border-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.feature_count} features)
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-300">Dataset B (Comparison)</label>
              <select
                value={datasetBId}
                onChange={(e) => setDatasetBId(e.target.value)}
                className="w-full bg-surface-950 border border-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.feature_count} features)
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={handleRunComparison}
              disabled={isExecuting || !datasetAId || !datasetBId}
              className="w-full mt-2 py-2 rounded bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>Run Two-Way Dataset Comparison</span>
            </button>
          </div>
        )}

        {/* Tab 4: Temporal Version Comparison */}
        {activeTab === 'temporal' && (
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-300">Dataset to Compare Across Versions</label>
              <select
                value={temporalDatasetId}
                onChange={(e) => setTemporalDatasetId(e.target.value)}
                className="w-full bg-surface-950 border border-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.feature_count} features)
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={handleRunVersionComparison}
              disabled={isExecuting || !temporalDatasetId}
              className="w-full py-2 rounded bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Clock className="w-4 h-4" />}
              <span>Compare Versions</span>
            </button>

            {versionResult && (
              <div className="mt-3 p-3 rounded-lg bg-surface-950 border border-border space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200">{versionResult.dataset_name}</span>
                  <span className="text-[10px] text-cyan-400 font-mono">
                    v{versionResult.version_a_number} → v{versionResult.version_b_number}
                  </span>
                </div>

                {versionResult.status === 'insufficient_versions' ? (
                  <p className="text-[11px] text-amber-300/90 bg-amber-950/30 p-2 rounded border border-amber-900/50">
                    {versionResult.message}
                  </p>
                ) : (
                  <div className="grid grid-cols-2 gap-2 text-center text-[11px]">
                    <div className="bg-emerald-950/40 border border-emerald-800/50 p-1.5 rounded">
                      <span className="text-emerald-400 font-bold block text-sm">{versionResult.added_count}</span>
                      <span className="text-slate-400 text-[9px]">ADDED</span>
                    </div>
                    <div className="bg-rose-950/40 border border-rose-800/50 p-1.5 rounded">
                      <span className="text-rose-400 font-bold block text-sm">{versionResult.removed_count}</span>
                      <span className="text-slate-400 text-[9px]">REMOVED</span>
                    </div>
                    <div className="bg-amber-950/40 border border-amber-800/50 p-1.5 rounded">
                      <span className="text-amber-400 font-bold block text-sm">{versionResult.changed_count}</span>
                      <span className="text-slate-400 text-[9px]">CHANGED</span>
                    </div>
                    <div className="bg-slate-900 border border-border p-1.5 rounded">
                      <span className="text-slate-300 font-bold block text-sm">{versionResult.unchanged_count}</span>
                      <span className="text-slate-400 text-[9px]">UNCHANGED</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Tab 5: Conflict Clusters */}
        {activeTab === 'conflicts' && (
          <div className="space-y-3">
            <p className="text-[11px] text-slate-400">
              Aggregates unresolved cross-source attribute conflicts into spatial hotspot clusters to prioritize human reconciliation.
            </p>

            <button
              onClick={handleRunConflictClustering}
              disabled={isExecuting}
              className="w-full py-2 rounded bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Flame className="w-4 h-4 fill-current" />}
              <span>Cluster Spatial Conflicts</span>
            </button>
          </div>
        )}

        {/* Tab 6: Buffer */}
        {activeTab === 'buffer' && (
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-300">Feature ID to Buffer (Optional)</label>
              <input
                type="text"
                placeholder="e.g. CAD-101 or UUID"
                value={bufferFeatureId}
                onChange={(e) => setBufferFeatureId(e.target.value)}
                className="w-full bg-surface-950 border border-border rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="space-y-1">
              <div className="flex justify-between items-center text-[11px]">
                <label className="font-semibold text-slate-300">Buffer Radius (Meters)</label>
                <span className="font-mono text-cyan-400">{bufferDistance} m</span>
              </div>
              <input
                type="range"
                min="10"
                max="500"
                step="10"
                value={bufferDistance}
                onChange={(e) => setBufferDistance(Number(e.target.value))}
                className="w-full accent-cyan-500"
              />
            </div>

            <button
              onClick={handleRunBuffer}
              disabled={isExecuting}
              className="w-full mt-2 py-2 rounded bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-semibold flex items-center justify-center gap-1.5 transition-colors"
            >
              {isExecuting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>Generate Spatial Buffer</span>
            </button>
          </div>
        )}

        {/* Tab 7: Analysis History */}
        {activeTab === 'history' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-300 text-[11px]">Recent Spatial Analyses</span>
              <span className="text-[10px] text-slate-500">{historyData?.length || 0} total</span>
            </div>

            {historyLoading ? (
              <div className="flex justify-center p-4">
                <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
              </div>
            ) : !historyData || historyData.length === 0 ? (
              <div className="text-center py-6 text-slate-500 text-[11px] bg-surface-950 rounded border border-border">
                No previous spatial analysis runs recorded in session.
              </div>
            ) : (
              <div className="space-y-2">
                {historyData.map((item) => (
                  <div
                    key={item.analysis_id}
                    className="p-2.5 rounded bg-surface-950 border border-border hover:border-cyan-500/50 transition-colors space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200 text-[11px] truncate max-w-[200px]" title={item.title}>
                        {item.title}
                      </span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/60 font-mono">
                        {item.analysis_type}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-slate-400">
                      <span>{item.result_count} features</span>
                      <span>{item.execution_time_ms.toFixed(1)} ms</span>
                    </div>

                    <div className="flex gap-1.5 pt-1">
                      <button
                        onClick={async () => {
                          const res = await api.getAnalysisById(item.analysis_id)
                          setActiveSpatialAnalysis(res)
                        }}
                        className="flex-1 py-1 rounded bg-surface-850 hover:bg-surface-800 text-cyan-300 font-medium text-[10px]"
                      >
                        View on Map
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 8: Statistics */}
        {activeTab === 'statistics' && (
          <div className="space-y-3">
            {statsLoading ? (
              <div className="flex items-center justify-center p-6">
                <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
              </div>
            ) : statsData ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-surface-950 p-2.5 rounded border border-border">
                    <span className="text-[10px] text-slate-500 block">TOTAL FEATURES</span>
                    <span className="text-sm font-bold text-slate-200">
                      {statsData.result_count.toLocaleString()}
                    </span>
                  </div>
                  <div className="bg-surface-950 p-2.5 rounded border border-border">
                    <span className="text-[10px] text-slate-500 block">GEOMETRY VALIDITY</span>
                    <span className="text-sm font-bold text-emerald-400">
                      {statsData.statistics.validity_percentage}% Valid
                    </span>
                  </div>
                  <div className="bg-surface-950 p-2.5 rounded border border-border">
                    <span className="text-[10px] text-slate-500 block">TOTAL AREA</span>
                    <span className="text-sm font-bold text-cyan-300">
                      {statsData.statistics.total_area_hectares} ha
                    </span>
                  </div>
                  <div className="bg-surface-950 p-2.5 rounded border border-border">
                    <span className="text-[10px] text-slate-500 block">EXECUTION TIME</span>
                    <span className="text-sm font-bold text-slate-300">
                      {statsData.execution_time_ms} ms
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => setActiveSpatialAnalysis(statsData)}
                  className="w-full py-1.5 rounded bg-surface-850 hover:bg-surface-800 border border-border text-cyan-300 font-semibold"
                >
                  Highlight Extent on Map
                </button>
              </div>
            ) : null}
          </div>
        )}

        {/* Active Analysis Result Banner & Export Actions */}
        {activeSpatialAnalysis && (
          <div className="mt-4 pt-3 border-t border-border space-y-2">
            <div className="bg-cyan-950/40 border border-cyan-800/80 rounded-lg p-3 space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                  <span className="font-bold text-cyan-300">{activeSpatialAnalysis.title}</span>
                </div>
                <button
                  onClick={clearActiveSpatialAnalysis}
                  className="text-slate-400 hover:text-slate-200"
                  title="Clear analysis layer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              <p className="text-[11px] text-slate-300">{activeSpatialAnalysis.description}</p>

              <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-cyan-900/50">
                <span>Features: <strong className="text-slate-200">{activeSpatialAnalysis.result_count}</strong></span>
                <span>Latency: <strong className="text-slate-200">{activeSpatialAnalysis.execution_time_ms} ms</strong></span>
              </div>

              {/* Action Buttons: Investigate & Export */}
              <div className="space-y-1.5 pt-1">
                <button
                  onClick={() => handleInvestigateWithAI(activeSpatialAnalysis)}
                  className="w-full py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-semibold flex items-center justify-center gap-1.5 transition-colors shadow-sm"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Investigate with AI</span>
                </button>

                <div className="grid grid-cols-2 gap-1.5">
                  <button
                    onClick={() => handleExport('geojson')}
                    className="py-1 px-2 rounded bg-surface-850 hover:bg-surface-800 border border-cyan-800/60 text-cyan-300 font-medium flex items-center justify-center gap-1 text-[10px]"
                    title="Export as RFC 7946 GeoJSON"
                  >
                    <FileCode2 className="w-3 h-3" />
                    <span>Export GeoJSON</span>
                  </button>

                  <button
                    onClick={() => handleExport('csv')}
                    className="py-1 px-2 rounded bg-surface-850 hover:bg-surface-800 border border-cyan-800/60 text-cyan-300 font-medium flex items-center justify-center gap-1 text-[10px]"
                    title="Export as Tabular CSV"
                  >
                    <FileSpreadsheet className="w-3 h-3" />
                    <span>Export CSV</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
