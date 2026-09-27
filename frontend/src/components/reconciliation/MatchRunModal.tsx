import React, { useState } from 'react'
import {
  X,
  Play,
  Settings,
  ChevronDown,
  ChevronUp,
  Loader2,
  Sliders,
  Database,
  Layers,
  Info,
} from 'lucide-react'
import { useStartMatchingRun } from '../../hooks/useMatching'
import type { Dataset, MatchingRunCreateInput } from '../../types'

interface MatchRunModalProps {
  projectId: string
  datasets: Dataset[]
  isOpen: boolean
  onClose: () => void
  onRunSuccess?: (runId: string) => void
}

export const MatchRunModal: React.FC<MatchRunModalProps> = ({
  projectId,
  datasets,
  isOpen,
  onClose,
  onRunSuccess,
}) => {
  const readyDatasets = datasets.filter((d) => d.status === 'ready' && d.feature_count > 0)

  const [sourceDatasetId, setSourceDatasetId] = useState<string>(
    readyDatasets.length > 0 ? readyDatasets[0].id : ''
  )
  const [candidateDatasetIds, setCandidateDatasetIds] = useState<string[]>(
    readyDatasets.length > 1 ? [readyDatasets[1].id] : []
  )

  const [showAdvanced, setShowAdvanced] = useState(false)
  const [searchDistance, setSearchDistance] = useState<number>(50.0)
  const [matchedThreshold, setMatchedThreshold] = useState<number>(0.80)
  const [possibleThreshold, setPossibleThreshold] = useState<number>(0.60)
  const [conflictThreshold, setConflictThreshold] = useState<number>(0.40)
  const [tieTolerance, setTieTolerance] = useState<number>(0.015)

  const startRunMutation = useStartMatchingRun(projectId)

  if (!isOpen) return null

  const handleToggleCandidate = (id: string) => {
    if (candidateDatasetIds.includes(id)) {
      setCandidateDatasetIds(candidateDatasetIds.filter((cid) => cid !== id))
    } else {
      setCandidateDatasetIds([...candidateDatasetIds, id])
    }
  }

  const handleSourceChange = (newSourceId: string) => {
    setSourceDatasetId(newSourceId)
    // Remove new source from candidates if present
    setCandidateDatasetIds(candidateDatasetIds.filter((cid) => cid !== newSourceId))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sourceDatasetId || candidateDatasetIds.length === 0) return

    const input: MatchingRunCreateInput = {
      source_dataset_id: sourceDatasetId,
      candidate_dataset_ids: candidateDatasetIds,
      configuration: {
        candidate_search_distance_meters: searchDistance,
        matched_threshold: matchedThreshold,
        possible_threshold: possibleThreshold,
        conflict_threshold: conflictThreshold,
        best_candidate_tie_tolerance: tieTolerance,
        spatial_weight: 0.35,
        area_weight: 0.20,
        centroid_weight: 0.20,
        geometry_weight: 0.15,
        attribute_weight: 0.10,
        scoring_version: 'v1.1',
      },
    }

    try {
      const run = await startRunMutation.mutateAsync(input)
      if (onRunSuccess) {
        onRunSuccess(run.id)
      }
      onClose()
    } catch (err) {
      // Error is handled by hook notification
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-surface-900 border border-border rounded-xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col font-mono text-xs">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-surface-950/60">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
              Execute Matching Analysis Run
            </h2>
          </div>
          <button
            onClick={onClose}
            disabled={startRunMutation.isPending}
            className="text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-5">
          {/* Source Dataset Selection */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-cyan-400" />
              <span>Primary Source Dataset (Reference)</span>
            </label>
            <select
              value={sourceDatasetId}
              onChange={(e) => handleSourceChange(e.target.value)}
              disabled={startRunMutation.isPending}
              className="w-full px-3 py-2 rounded-lg bg-surface-950 border border-border text-slate-200 focus:outline-none focus:border-cyan-500 font-mono text-xs"
            >
              {readyDatasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.geometry_type}, {d.feature_count} feats)
                </option>
              ))}
            </select>
            <p className="text-[10px] text-slate-400 font-sans">
              Each feature from this dataset will search for spatial candidates in the target datasets.
            </p>
          </div>

          {/* Candidate Datasets Selection */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-amber-400" />
              <span>Candidate Datasets (Compare Against)</span>
            </label>
            <div className="space-y-1.5 max-h-36 overflow-y-auto bg-surface-950 p-2.5 rounded-lg border border-border">
              {readyDatasets
                .filter((d) => d.id !== sourceDatasetId)
                .map((d) => {
                  const isChecked = candidateDatasetIds.includes(d.id)
                  return (
                    <label
                      key={d.id}
                      className="flex items-center gap-2.5 p-1.5 rounded hover:bg-surface-850 cursor-pointer transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => handleToggleCandidate(d.id)}
                        disabled={startRunMutation.isPending}
                        className="rounded border-border bg-surface-900 text-cyan-500 focus:ring-cyan-500"
                      />
                      <span className="text-slate-200 text-xs font-semibold">{d.name}</span>
                      <span className="text-slate-400 text-[10px]">
                        ({d.geometry_type}, {d.feature_count} feats)
                      </span>
                    </label>
                  )
                })}
              {readyDatasets.filter((d) => d.id !== sourceDatasetId).length === 0 && (
                <p className="text-[11px] text-slate-500 italic p-2 text-center">
                  No other datasets available in this project. Upload another dataset first.
                </p>
              )}
            </div>
          </div>

          {/* Advanced Matching Parameters Accordion */}
          <div className="border border-border/80 rounded-lg overflow-hidden bg-surface-950/40">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full px-3 py-2 flex items-center justify-between text-[11px] text-slate-400 hover:text-slate-200 font-semibold uppercase tracking-wider bg-surface-950/60"
            >
              <div className="flex items-center gap-1.5">
                <Settings className="w-3.5 h-3.5 text-slate-400" />
                <span>Configurable Tolerances & Thresholds</span>
              </div>
              {showAdvanced ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>

            {showAdvanced && (
              <div className="p-3.5 space-y-3 border-t border-border/80 text-xs">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-slate-400">Search Tolerance:</span>
                    <span className="text-cyan-300 font-bold">{searchDistance} meters</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="500"
                    step="5"
                    value={searchDistance}
                    onChange={(e) => setSearchDistance(parseFloat(e.target.value))}
                    className="w-full accent-cyan-500"
                  />
                  <p className="text-[10px] text-slate-500 font-sans">
                    PostGIS GIST buffer radius for candidate feature generation.
                  </p>
                </div>

                <div className="grid grid-cols-4 gap-2 text-[10px]">
                  <div>
                    <span className="text-slate-400 block mb-1">MATCHED &ge;</span>
                    <input
                      type="number"
                      step="0.05"
                      min="0.5"
                      max="0.99"
                      value={matchedThreshold}
                      onChange={(e) => setMatchedThreshold(parseFloat(e.target.value))}
                      className="w-full px-2 py-1 rounded bg-surface-950 border border-border text-slate-200"
                    />
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-1">POSSIBLE &ge;</span>
                    <input
                      type="number"
                      step="0.05"
                      min="0.4"
                      max="0.8"
                      value={possibleThreshold}
                      onChange={(e) => setPossibleThreshold(parseFloat(e.target.value))}
                      className="w-full px-2 py-1 rounded bg-surface-950 border border-border text-slate-200"
                    />
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-1">CONFLICT &ge;</span>
                    <input
                      type="number"
                      step="0.05"
                      min="0.2"
                      max="0.6"
                      value={conflictThreshold}
                      onChange={(e) => setConflictThreshold(parseFloat(e.target.value))}
                      className="w-full px-2 py-1 rounded bg-surface-950 border border-border text-slate-200"
                    />
                  </div>
                  <div>
                    <span className="text-slate-400 block mb-1" title="Top candidates within this score margin are marked AMBIGUOUS">TIE TOL &le;</span>
                    <input
                      type="number"
                      step="0.005"
                      min="0.005"
                      max="0.1"
                      value={tieTolerance}
                      onChange={(e) => setTieTolerance(parseFloat(e.target.value))}
                      className="w-full px-2 py-1 rounded bg-surface-950 border border-border text-amber-300 font-mono"
                    />
                  </div>
                </div>

                <div className="p-2 rounded bg-surface-900 border border-border text-[10px] text-slate-400 flex items-start gap-1.5 font-sans">
                  <Info className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0 mt-0.5" />
                  <span>
                    Signals: Spatial Overlap (35%), Centroid Proximity (20%), Area Similarity (20%), Geometry Similarity (15%), Attribute Alignment (10%). Non-applicable signals are dynamically renormalized.
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={startRunMutation.isPending}
              className="px-3.5 py-1.5 rounded-lg border border-border text-slate-400 hover:text-slate-200 hover:bg-surface-850 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!sourceDatasetId || candidateDatasetIds.length === 0 || startRunMutation.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-semibold shadow-lg shadow-cyan-950/50 transition-all"
            >
              {startRunMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Evaluating Spatial Candidates...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white" />
                  <span>Run Reconciliation Analysis</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
