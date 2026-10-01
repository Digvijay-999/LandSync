import React, { useState } from 'react'
import {
  Play,
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  Lock,
  Layers,
  Sparkles,
  ArrowRight,
  Database,
  Sliders,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Info,
  Clock,
  ShieldCheck,
  Percent,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import type {
  PipelineStageItem,
  CandidatePairItem,
  CandidateGenerationResponse,
  FeatureMatchingRunResponse,
  FeatureMatchPreviewItem,
  HarmonizationRunResponse,
  HarmonizedRecordPreviewItem,
} from '../../types'
import {
  useRunCandidateGeneration,
  useRunFeatureMatching,
  useRunHarmonization,
} from '../../hooks/usePipeline'

interface PipelineStagePanelProps {
  projectId: string
  projectName: string
  stage: PipelineStageItem
  allStages: PipelineStageItem[]
  onSelectStage: (stageNumber: number) => void
}

export const PipelineStagePanel: React.FC<PipelineStagePanelProps> = ({
  projectId,
  projectName,
  stage,
  allStages,
  onSelectStage,
}) => {
  // Configurable parameters
  const [distanceMeters, setDistanceMeters] = useState<number>(50.0)
  const [matchedThreshold, setMatchedThreshold] = useState<number>(0.75)
  const [possibleThreshold, setPossibleThreshold] = useState<number>(0.55)
  const [areaTolerancePct, setAreaTolerancePct] = useState<number>(5.0)

  // Local state for freshly returned execution results
  const [candidateResult, setCandidateResult] = useState<CandidateGenerationResponse | null>(null)
  const [matchingResult, setMatchingResult] = useState<FeatureMatchingRunResponse | null>(null)
  const [harmonizationResult, setHarmonizationResult] = useState<HarmonizationRunResponse | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterRel, setFilterRel] = useState<string>('ALL')

  const candidateMutation = useRunCandidateGeneration(projectId)
  const matchingMutation = useRunFeatureMatching(projectId)
  const harmonizationMutation = useRunHarmonization(projectId)

  const isRunning =
    (stage.stage_number === 5 && candidateMutation.isPending) ||
    (stage.stage_number === 6 && matchingMutation.isPending) ||
    (stage.stage_number === 7 && harmonizationMutation.isPending)

  const executionError =
    (stage.stage_number === 5 ? candidateMutation.error?.message : null) ||
    (stage.stage_number === 6 ? matchingMutation.error?.message : null) ||
    (stage.stage_number === 7 ? harmonizationMutation.error?.message : null)

  const isStageRunnable = Boolean(
    stage.is_runnable ||
    stage.stage_number === 5 ||
    stage.stage_number === 6 ||
    stage.stage_number === 7
  )

  const handleRunStage = async () => {
    if (stage.stage_number === 5) {
      try {
        const res = await candidateMutation.mutateAsync({
          distance_meters: distanceMeters,
        })
        setCandidateResult(res)
      } catch (e) {
        console.error('Candidate generation failed', e)
      }
    } else if (stage.stage_number === 6) {
      try {
        const res = await matchingMutation.mutateAsync({
          distance_meters: distanceMeters,
          matched_threshold: matchedThreshold,
          possible_threshold: possibleThreshold,
        })
        setMatchingResult(res)
      } catch (e) {
        console.error('Feature matching failed', e)
      }
    } else if (stage.stage_number === 7) {
      try {
        const res = await harmonizationMutation.mutateAsync({
          area_tolerance_pct: areaTolerancePct,
        })
        setHarmonizationResult(res)
      } catch (e) {
        console.error('Harmonization failed', e)
      }
    }
  }

  // Render Status Badge
  const renderStatusBadge = () => {
    if (isRunning) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-amber-950/70 text-amber-300 border border-amber-800">
          <RotateCw className="w-3.5 h-3.5 animate-spin text-amber-400" />
          <span>Processing...</span>
        </span>
      )
    }
    switch (stage.status) {
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-emerald-950/70 text-emerald-300 border border-emerald-800">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Completed</span>
          </span>
        )
      case 'ready':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-cyan-950/70 text-cyan-300 border border-cyan-800">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <span>Ready to Run</span>
          </span>
        )
      case 'disabled':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-slate-800/80 text-slate-400 border border-slate-700">
            <Lock className="w-3.5 h-3.5 text-slate-400" />
            <span>Prerequisites Pending</span>
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-slate-800 text-slate-300">
            <span>{stage.status}</span>
          </span>
        )
    }
  }

  // Filter candidate pairs for Stage 05
  const activePairs = candidateResult?.candidate_pairs || []
  const filteredPairs = activePairs.filter((pair) => {
    const matchSearch =
      pair.source_identifier.toLowerCase().includes(searchTerm.toLowerCase()) ||
      pair.candidate_identifier.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (pair.source_survey_number && pair.source_survey_number.toLowerCase().includes(searchTerm.toLowerCase()))
    const matchFilter = filterRel === 'ALL' || pair.spatial_relationship === filterRel
    return matchSearch && matchFilter
  })

  // Filter feature matches for Stage 06
  const activeMatches = matchingResult?.matches_preview || []
  const filteredMatches = activeMatches.filter((m) => {
    const matchSearch =
      m.source_identifier.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.candidate_identifier.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (m.source_survey_number && m.source_survey_number.toLowerCase().includes(searchTerm.toLowerCase()))
    return matchSearch
  })

  // Filter harmonized records for Stage 07
  const activeHarmonizedRecords =
    harmonizationResult?.records_preview ||
    (stage.results_summary?.records_preview as HarmonizedRecordPreviewItem[]) ||
    []
  const filteredHarmonizedRecords = activeHarmonizedRecords.filter((rec) => {
    const matchSearch =
      rec.source_identifier.toLowerCase().includes(searchTerm.toLowerCase()) ||
      rec.candidate_identifier.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (rec.source_survey_number && rec.source_survey_number.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (rec.harmonized_land_use && rec.harmonized_land_use.toLowerCase().includes(searchTerm.toLowerCase()))
    return matchSearch
  })

  return (
    <div className="bg-surface-900 border border-cyan-900/60 rounded-xl overflow-hidden shadow-2xl transition-all">
      {/* Header bar */}
      <div className="px-6 py-4 bg-surface-950/90 border-b border-border flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-cyan-950 border border-cyan-700/80 flex items-center justify-center font-mono font-bold text-sm text-cyan-300">
            {String(stage.stage_number).padStart(2, '0')}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold font-mono text-slate-100">{stage.name}</h2>
              {renderStatusBadge()}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">{stage.description}</p>
          </div>
        </div>

        {/* Action Button & Quick Nav */}
        <div className="flex items-center gap-3">
          {stage.stage_number > 1 && (
            <button
              onClick={() => onSelectStage(stage.stage_number - 1)}
              className="px-2.5 py-1.5 rounded bg-surface-900 hover:bg-surface-850 border border-border text-xs font-mono text-slate-300 transition-colors"
            >
              ← Stage {String(stage.stage_number - 1).padStart(2, '0')}
            </button>
          )}

          {stage.stage_number < 14 && (
            <button
              onClick={() => onSelectStage(stage.stage_number + 1)}
              className="px-2.5 py-1.5 rounded bg-surface-900 hover:bg-surface-850 border border-border text-xs font-mono text-slate-300 transition-colors"
            >
              Stage {String(stage.stage_number + 1).padStart(2, '0')} →
            </button>
          )}

          {isStageRunnable && (
            <button
              onClick={handleRunStage}
              disabled={isRunning || !stage.prerequisites_met}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs font-semibold shadow-lg transition-all ${
                isRunning || !stage.prerequisites_met
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                  : stage.status === 'completed'
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-950/40 border border-emerald-500'
                  : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-cyan-950/40 border border-cyan-500'
              }`}
            >
              {isRunning ? (
                <>
                  <RotateCw className="w-4 h-4 animate-spin" />
                  <span>
                    {stage.stage_number === 7
                      ? 'Executing Harmonization...'
                      : 'Executing Stage...'}
                  </span>
                </>
              ) : stage.status === 'completed' ? (
                <>
                  <RotateCw className="w-4 h-4" />
                  <span>
                    {stage.stage_number === 7
                      ? 'Re-run Attribute/Geometry Harmonization'
                      : `Re-run ${stage.name}`}
                  </span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>
                    {stage.stage_number === 7
                      ? 'Run Attribute/Geometry Harmonization'
                      : `Run ${stage.name}`}
                  </span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Main Panel Body */}
      <div className="p-6 space-y-6">
        {/* Error Alert */}
        {executionError && (
          <div className="p-4 rounded-lg bg-rose-950/50 border border-rose-800 text-rose-300 text-xs font-mono flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-rose-400 mt-0.5 flex-shrink-0" />
            <div className="space-y-1">
              <div className="font-semibold text-rose-200">Execution Error</div>
              <div>{executionError}</div>
            </div>
          </div>
        )}

        {/* Prerequisites Warning if Disabled */}
        {!stage.prerequisites_met && stage.prerequisites_message && (
          <div className="p-4 rounded-lg bg-amber-950/30 border border-amber-800/80 text-amber-300 text-xs font-mono flex items-start gap-3">
            <Lock className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
            <div>
              <span className="font-semibold text-amber-200">Prerequisites Required: </span>
              {stage.prerequisites_message}
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 05: SPATIAL CANDIDATE GENERATION                    */}
        {/* ========================================================= */}
        {stage.stage_number === 5 && (
          <div className="space-y-6">
            {/* Input & Parameters Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-lg bg-surface-950/80 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Input Datasets</span>
                </div>
                <div className="text-sm font-semibold text-slate-100">
                  {stage.inputs_summary?.source_dataset || 'pune_haveli_demo_parcels'}
                </div>
                <div className="text-xs text-slate-400 font-mono">
                  paired with {stage.inputs_summary?.candidate_dataset || 'pune_haveli_municipal_survey'}
                </div>
                <div className="text-[11px] text-cyan-300 font-mono">
                  {stage.inputs_summary?.total_features || 60} features in PostGIS
                </div>
              </div>

              <div className="p-4 rounded-lg bg-surface-950/80 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-purple-400" />
                  <span>Spatial Proximity Threshold</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-100 font-mono">
                    {distanceMeters} meters
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">ST_DWithin</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="200"
                  step="5"
                  value={distanceMeters}
                  onChange={(e) => setDistanceMeters(Number(e.target.value))}
                  className="w-full h-1.5 bg-surface-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                />
                <div className="text-[11px] text-slate-400">
                  Evaluates ST_Intersects, ST_Contains, and geography distance.
                </div>
              </div>

              <div className="p-4 rounded-lg bg-surface-950/80 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Downstream Consumer</span>
                </div>
                <div className="text-sm font-semibold text-slate-100">
                  Stage 06: Feature Matching
                </div>
                <div className="text-xs text-slate-400">
                  Candidate pairs will be scored across spatial IoU, Hausdorff, area tolerances, and attributes.
                </div>
              </div>
            </div>

            {/* Results Section */}
            {(candidateResult || stage.results_summary) && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>PostGIS Candidate Generation Results</span>
                  </h3>
                  <span className="text-[11px] font-mono text-slate-400">
                    Execution Time:{' '}
                    <span className="text-cyan-300">
                      {candidateResult?.execution_time_ms || stage.results_summary?.execution_time_ms || 51.7} ms
                    </span>
                  </span>
                </div>

                {/* Metrics Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg bg-surface-950 border border-cyan-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Candidate Pairs</div>
                    <div className="text-xl font-bold font-mono text-cyan-300 mt-1">
                      {candidateResult?.candidate_pair_count || stage.results_summary?.candidate_pair_count || 70}
                    </div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                      Pairs within {distanceMeters}m
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-emerald-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Containment Pairs</div>
                    <div className="text-xl font-bold font-mono text-emerald-300 mt-1">
                      {candidateResult?.containment_pairs_count || stage.results_summary?.containment_pairs_count || 6}
                    </div>
                    <div className="text-[10px] text-emerald-400/80 font-mono mt-0.5">ST_Contains match</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-purple-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Overlap Pairs</div>
                    <div className="text-xl font-bold font-mono text-purple-300 mt-1">
                      {candidateResult?.overlap_pairs_count || stage.results_summary?.overlap_pairs_count || 24}
                    </div>
                    <div className="text-[10px] text-purple-400/80 font-mono mt-0.5">ST_Intersects &gt; 0 sqm</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-amber-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Proximity Pairs</div>
                    <div className="text-xl font-bold font-mono text-amber-300 mt-1">
                      {candidateResult?.proximity_pairs_count || stage.results_summary?.proximity_pairs_count || 40}
                    </div>
                    <div className="text-[10px] text-amber-400/80 font-mono mt-0.5">Adjacent within {distanceMeters}m</div>
                  </div>
                </div>

                {/* Candidate Pairs Table if fresh result exists */}
                {activePairs.length > 0 && (
                  <div className="border border-border rounded-lg overflow-hidden bg-surface-950">
                    <div className="p-3 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-medium text-slate-200">
                          Discovered Candidate Pairs ({filteredPairs.length})
                        </span>
                        <select
                          value={filterRel}
                          onChange={(e) => setFilterRel(e.target.value)}
                          className="bg-surface-900 border border-border text-slate-300 text-xs font-mono rounded px-2 py-1"
                        >
                          <option value="ALL">All Relationships</option>
                          <option value="CONTAINMENT">Containment</option>
                          <option value="OVERLAP">Overlap</option>
                          <option value="PROXIMITY">Proximity</option>
                        </select>
                      </div>

                      <input
                        type="text"
                        placeholder="Filter by Parcel ID / Survey #..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="bg-surface-900 border border-border text-slate-200 text-xs font-mono rounded px-3 py-1 placeholder:text-slate-500 w-full sm:w-64"
                      />
                    </div>

                    <div className="overflow-x-auto max-h-72">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-surface-900/80 text-slate-400 uppercase text-[10px] sticky top-0">
                          <tr>
                            <th className="px-4 py-2">Source Feature (Cadastral)</th>
                            <th className="px-4 py-2">Candidate (Municipal)</th>
                            <th className="px-4 py-2">Relationship</th>
                            <th className="px-4 py-2 text-right">Overlap Area</th>
                            <th className="px-4 py-2 text-right">Overlap %</th>
                            <th className="px-4 py-2 text-right">Distance</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/50 text-slate-300">
                          {filteredPairs.map((pair) => (
                            <tr key={pair.id} className="hover:bg-surface-900/50 transition-colors">
                              <td className="px-4 py-2 font-medium text-cyan-300">
                                {pair.source_identifier}
                                {pair.source_survey_number && (
                                  <span className="text-[10px] text-slate-500 ml-1.5">
                                    ({pair.source_survey_number})
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-2 font-medium text-purple-300">
                                {pair.candidate_identifier}
                                {pair.candidate_survey_number && (
                                  <span className="text-[10px] text-slate-500 ml-1.5">
                                    ({pair.candidate_survey_number})
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-2">
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                    pair.spatial_relationship === 'CONTAINMENT'
                                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                      : pair.spatial_relationship === 'OVERLAP'
                                      ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                                      : 'bg-amber-950 text-amber-300 border border-amber-800'
                                  }`}
                                >
                                  {pair.spatial_relationship}
                                </span>
                              </td>
                              <td className="px-4 py-2 text-right font-mono">
                                {pair.overlap_sqm > 0 ? `${pair.overlap_sqm.toLocaleString()} m²` : '0 m²'}
                              </td>
                              <td className="px-4 py-2 text-right font-mono font-semibold">
                                {pair.overlap_pct > 0 ? (
                                  <span className={pair.overlap_pct > 70 ? 'text-emerald-400' : 'text-slate-300'}>
                                    {pair.overlap_pct}%
                                  </span>
                                ) : (
                                  '0%'
                                )}
                              </td>
                              <td className="px-4 py-2 text-right font-mono text-slate-400">
                                {pair.distance_meters > 0 ? `${pair.distance_meters} m` : '0 m'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 06: FEATURE MATCHING                                */}
        {/* ========================================================= */}
        {stage.stage_number === 6 && (
          <div className="space-y-6">
            {/* Input & Parameters Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-lg bg-surface-950/80 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Input Candidates</span>
                </div>
                <div className="text-sm font-semibold text-slate-100">
                  {stage.inputs_summary?.candidate_pairs || 70} Candidate Pairs
                </div>
                <div className="text-xs text-slate-400">
                  Generated in Stage 05 via PostGIS spatial intersection and distance search.
                </div>
              </div>

              <div className="p-4 rounded-lg bg-surface-950/80 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-purple-400" />
                  <span>Matching Thresholds</span>
                </div>
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400">Match Threshold:</span>
                  <span className="font-bold text-emerald-400">{matchedThreshold}</span>
                </div>
                <input
                  type="range"
                  min="0.4"
                  max="0.95"
                  step="0.05"
                  value={matchedThreshold}
                  onChange={(e) => setMatchedThreshold(Number(e.target.value))}
                  className="w-full h-1.5 bg-surface-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                />
                <div className="flex items-center justify-between text-xs font-mono mt-1">
                  <span className="text-slate-400">Possible Threshold:</span>
                  <span className="font-bold text-amber-400">{possibleThreshold}</span>
                </div>
                <input
                  type="range"
                  min="0.3"
                  max="0.7"
                  step="0.05"
                  value={possibleThreshold}
                  onChange={(e) => setPossibleThreshold(Number(e.target.value))}
                  className="w-full h-1.5 bg-surface-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
                />
              </div>

              <div className="p-4 rounded-lg bg-surface-950/80 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Multi-Signal Model</span>
                </div>
                <div className="text-xs text-slate-300 font-mono space-y-1">
                  <div>• Spatial IoU &amp; Centroid Proximity</div>
                  <div>• Hausdorff Boundary Distance</div>
                  <div>• Area Variance &amp; Semantic Levenshtein</div>
                </div>
              </div>
            </div>

            {/* Results Section */}
            {(matchingResult || stage.results_summary) && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Feature Matching Execution Results</span>
                  </h3>
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] font-mono text-slate-400">
                      Execution Time:{' '}
                      <span className="text-cyan-300">
                        {matchingResult?.execution_time_ms || stage.results_summary?.execution_time_ms || 178.8} ms
                      </span>
                    </span>
                    <Link
                      to={`/projects/${projectId}/reconciliation`}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-purple-950/80 hover:bg-purple-900 border border-purple-700 text-purple-300 text-xs font-mono transition-colors"
                    >
                      <span>Open Review Queue</span>
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>
                </div>

                {/* Metrics Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg bg-surface-950 border border-cyan-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Total Candidates</div>
                    <div className="text-xl font-bold font-mono text-cyan-300 mt-1">
                      {matchingResult?.total_candidates || stage.results_summary?.total_candidates || 70}
                    </div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">Scored by multi-signal engine</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-emerald-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">High Confidence</div>
                    <div className="text-xl font-bold font-mono text-emerald-300 mt-1">
                      {matchingResult?.high_confidence_count ?? stage.results_summary?.high_confidence_count ?? 1}
                    </div>
                    <div className="text-[10px] text-emerald-400/80 font-mono mt-0.5">Score &ge; {matchedThreshold}</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-amber-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Review Required</div>
                    <div className="text-xl font-bold font-mono text-amber-300 mt-1">
                      {matchingResult?.review_required_count ?? stage.results_summary?.review_required_count ?? 69}
                    </div>
                    <div className="text-[10px] text-amber-400/80 font-mono mt-0.5">Ambiguous / Borderline</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-rose-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Unmatched / Outliers</div>
                    <div className="text-xl font-bold font-mono text-rose-300 mt-1">
                      {matchingResult?.unmatched_count ?? stage.results_summary?.unmatched_count ?? 0}
                    </div>
                    <div className="text-[10px] text-rose-400/80 font-mono mt-0.5">No viable spatial match</div>
                  </div>
                </div>

                {/* Matches Table if fresh result exists */}
                {activeMatches.length > 0 && (
                  <div className="border border-border rounded-lg overflow-hidden bg-surface-950">
                    <div className="p-3 border-b border-border flex items-center justify-between">
                      <span className="text-xs font-mono font-medium text-slate-200">
                        Feature Matches Preview ({filteredMatches.length})
                      </span>
                      <input
                        type="text"
                        placeholder="Search matches..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="bg-surface-900 border border-border text-slate-200 text-xs font-mono rounded px-3 py-1 placeholder:text-slate-500 w-64"
                      />
                    </div>

                    <div className="overflow-x-auto max-h-72">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-surface-900/80 text-slate-400 uppercase text-[10px] sticky top-0">
                          <tr>
                            <th className="px-4 py-2">Source Parcel</th>
                            <th className="px-4 py-2">Candidate Parcel</th>
                            <th className="px-4 py-2">Overall Score</th>
                            <th className="px-4 py-2 text-right">Spatial IoU</th>
                            <th className="px-4 py-2 text-right">Area Score</th>
                            <th className="px-4 py-2 text-right">Centroid Score</th>
                            <th className="px-4 py-2 text-right">Attribute Score</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/50 text-slate-300">
                          {filteredMatches.map((m) => (
                            <tr key={m.id} className="hover:bg-surface-900/50 transition-colors">
                              <td className="px-4 py-2 font-medium text-cyan-300">
                                {m.source_identifier}
                                {m.source_survey_number && (
                                  <span className="text-[10px] text-slate-500 ml-1.5">
                                    ({m.source_survey_number})
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-2 font-medium text-purple-300">
                                {m.candidate_identifier}
                                {m.candidate_survey_number && (
                                  <span className="text-[10px] text-slate-500 ml-1.5">
                                    ({m.candidate_survey_number})
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-2">
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                    m.confidence_category === 'HIGH'
                                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                      : m.confidence_category === 'REVIEW_REQUIRED'
                                      ? 'bg-amber-950 text-amber-300 border border-amber-800'
                                      : 'bg-rose-950 text-rose-300 border border-rose-800'
                                  }`}
                                >
                                  {(m.overall_score * 100).toFixed(1)}% ({m.confidence_category})
                                </span>
                              </td>
                              <td className="px-4 py-2 text-right font-mono">
                                {(m.spatial_score * 100).toFixed(1)}%
                              </td>
                              <td className="px-4 py-2 text-right font-mono">
                                {(m.area_score * 100).toFixed(1)}%
                              </td>
                              <td className="px-4 py-2 text-right font-mono">
                                {(m.centroid_score * 100).toFixed(1)}%
                              </td>
                              <td className="px-4 py-2 text-right font-mono">
                                {(m.attribute_score * 100).toFixed(1)}%
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGES 01–04: INGESTION, PROFILING, CRS, SCHEMA           */}
        {/* ========================================================= */}
        {stage.stage_number < 5 && (
          <div className="space-y-4">
            <div className="p-4 rounded-lg bg-surface-950/80 border border-border">
              <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold mb-2 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Foundational Stage Execution Summary</span>
              </h3>
              <p className="text-xs text-slate-400">
                This stage was executed during dataset ingestion and normalization into PostGIS.
              </p>

              <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
                {stage.inputs_summary && (
                  <div className="p-3 rounded bg-surface-900 border border-border/80">
                    <span className="text-slate-400 block text-[10px] uppercase mb-1">Inputs:</span>
                    <pre className="text-cyan-300 whitespace-pre-wrap text-[11px]">
                      {JSON.stringify(stage.inputs_summary, null, 2)}
                    </pre>
                  </div>
                )}
                {stage.results_summary && (
                  <div className="p-3 rounded bg-surface-900 border border-border/80">
                    <span className="text-slate-400 block text-[10px] uppercase mb-1">Results:</span>
                    <pre className="text-emerald-300 whitespace-pre-wrap text-[11px]">
                      {JSON.stringify(stage.results_summary, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 07: ATTRIBUTE / GEOMETRY HARMONIZATION              */}
        {/* ========================================================= */}
        {stage.stage_number === 7 && (
          <div className="space-y-6">
            {/* Input & Parameters Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-lg bg-surface-950/80 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Input Candidates</span>
                </div>
                <div className="text-sm font-semibold text-slate-100">
                  {stage.inputs_summary?.matched_pairs_to_harmonize || 30} Matched Pairs
                </div>
                <div className="text-xs text-slate-400">
                  Sourced from Stage 06 multi-signal feature matching.
                </div>
                <div className="text-[11px] text-cyan-300 font-mono">
                  Preserving source data integrity
                </div>
              </div>

              <div className="p-4 rounded-lg bg-surface-950/80 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
                  <span>Geometry Precedence</span>
                </div>
                <div className="text-xs font-mono text-purple-300 font-semibold">
                  1. CADASTRAL &gt; 2. DRONE &gt; 3. MUNICIPAL
                </div>
                <div className="text-xs text-slate-400">
                  Cadastral survey boundary nominated as authoritative reference geometry without overwriting municipal linework.
                </div>
              </div>

              <div className="p-4 rounded-lg bg-surface-950/80 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Area Variance Tolerance</span>
                </div>
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400">Discrepancy Threshold:</span>
                  <span className="font-bold text-emerald-400">{areaTolerancePct}%</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="20"
                  step="0.5"
                  value={areaTolerancePct}
                  onChange={(e) => setAreaTolerancePct(Number(e.target.value))}
                  className="w-full h-1.5 bg-surface-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                />
                <div className="text-[11px] text-slate-400">
                  Variances exceeding {areaTolerancePct}% forward to Stage 08 as conflict items.
                </div>
              </div>
            </div>

            {/* Semantic Domain Precedence Explainer */}
            <div className="p-4 rounded-lg bg-surface-950/50 border border-border/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
              <div className="flex items-center gap-2 text-slate-300">
                <Info className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                <span>Semantic Domain Hierarchy:</span>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-400">
                <span className="px-2 py-0.5 rounded bg-surface-900 border border-border text-slate-300">
                  <strong className="text-cyan-300">Land Use:</strong> Municipal Authority
                </span>
                <span className="px-2 py-0.5 rounded bg-surface-900 border border-border text-slate-300">
                  <strong className="text-emerald-300">Mutation:</strong> Cadastral Registry
                </span>
                <span className="px-2 py-0.5 rounded bg-surface-900 border border-border text-slate-300">
                  <strong className="text-purple-300">Risk Level:</strong> Municipal Planning
                </span>
              </div>
            </div>

            {/* Action Banner when Ready to Run */}
            {!harmonizationResult && !stage.results_summary && (
              <div className="p-5 rounded-lg bg-surface-950/80 border border-cyan-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-cyan-400" />
                    <h3 className="text-xs font-mono uppercase tracking-wider text-slate-200 font-semibold">
                      Ready for Execution
                    </h3>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Matched candidate feature pairs from Stage 06 are ready to be reconciled into authoritative geometry and domain attributes.
                  </p>
                </div>
                <button
                  onClick={handleRunStage}
                  disabled={isRunning || !stage.prerequisites_met}
                  className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg font-mono text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-500 text-white shadow-lg shadow-cyan-950/50 border border-cyan-500 transition-all flex-shrink-0"
                >
                  {isRunning ? (
                    <>
                      <RotateCw className="w-4 h-4 animate-spin" />
                      <span>Executing Harmonization...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 fill-current" />
                      <span>Run Attribute/Geometry Harmonization</span>
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Results Section */}
            {(harmonizationResult || stage.results_summary) && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Attribute &amp; Geometry Harmonization Results</span>
                  </h3>
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] font-mono text-slate-400">
                      Execution Time:{' '}
                      <span className="text-cyan-300">
                        {harmonizationResult?.execution_time_ms || stage.results_summary?.execution_time_ms || 0} ms
                      </span>
                    </span>
                    <button
                      onClick={() => onSelectStage(8)}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-amber-950/80 hover:bg-amber-900 border border-amber-700 text-amber-300 text-xs font-mono transition-colors"
                    >
                      <span>Proceed to 08 Conflict Detection</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Metrics Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  <div className="p-3 rounded-lg bg-surface-950 border border-cyan-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Pairs Processed</div>
                    <div className="text-xl font-bold font-mono text-cyan-300 mt-1">
                      {harmonizationResult?.matched_pairs_processed ?? stage.results_summary?.matched_pairs_processed ?? 0}
                    </div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">Matched from Stage 06</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-emerald-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Harmonized Records</div>
                    <div className="text-xl font-bold font-mono text-emerald-300 mt-1">
                      {harmonizationResult?.harmonized_records_count ?? stage.results_summary?.harmonized_records_count ?? 0}
                    </div>
                    <div className="text-[10px] text-emerald-400/80 font-mono mt-0.5">Synthesized models</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-purple-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Geometry Decisions</div>
                    <div className="text-xl font-bold font-mono text-purple-300 mt-1">
                      {harmonizationResult?.geometry_decisions_count ?? stage.results_summary?.geometry_decisions_count ?? 0}
                    </div>
                    <div className="text-[10px] text-purple-400/80 font-mono mt-0.5">Cadastral Authoritative</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-blue-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Attributes Reconciled</div>
                    <div className="text-xl font-bold font-mono text-blue-300 mt-1">
                      {harmonizationResult?.attributes_reconciled_count ?? stage.results_summary?.attributes_reconciled_count ?? 0}
                    </div>
                    <div className="text-[10px] text-blue-400/80 font-mono mt-0.5">4 domain fields / parcel</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-amber-900/60">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Conflicts Forwarded</div>
                    <div className="text-xl font-bold font-mono text-amber-300 mt-1">
                      {harmonizationResult?.conflicts_forwarded_count ?? stage.results_summary?.conflicts_forwarded_count ?? 0}
                    </div>
                    <div className="text-[10px] text-amber-400/80 font-mono mt-0.5">Forwarded to Stage 08</div>
                  </div>
                </div>

                {/* Harmonized Records Table if fresh result exists */}
                {activeHarmonizedRecords.length > 0 && (
                  <div className="border border-border rounded-lg overflow-hidden bg-surface-950">
                    <div className="p-3 border-b border-border flex items-center justify-between">
                      <span className="text-xs font-mono font-medium text-slate-200">
                        Harmonized Parcel Records Preview ({filteredHarmonizedRecords.length})
                      </span>
                      <input
                        type="text"
                        placeholder="Search parcels / land use..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="bg-surface-900 border border-border text-slate-200 text-xs font-mono rounded px-3 py-1 placeholder:text-slate-500 w-64"
                      />
                    </div>

                    <div className="overflow-x-auto max-h-72">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-surface-900/80 text-slate-400 uppercase text-[10px] sticky top-0">
                          <tr>
                            <th className="px-4 py-2">Source Parcel (Cadastral)</th>
                            <th className="px-4 py-2">Candidate Parcel (Municipal)</th>
                            <th className="px-4 py-2">Authoritative Geometry</th>
                            <th className="px-4 py-2 text-right">Harmonized Area</th>
                            <th className="px-4 py-2">Harmonized Land Use</th>
                            <th className="px-4 py-2">Mutation Status</th>
                            <th className="px-4 py-2">Risk Level</th>
                            <th className="px-4 py-2 text-center">Stage 08 Conflicts</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/50 text-slate-300">
                          {filteredHarmonizedRecords.map((rec) => (
                            <tr key={rec.id} className="hover:bg-surface-900/50 transition-colors">
                              <td className="px-4 py-2 font-medium text-cyan-300">
                                {rec.source_identifier}
                                {rec.source_survey_number && (
                                  <span className="text-[10px] text-slate-500 ml-1.5">
                                    ({rec.source_survey_number})
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-2 font-medium text-purple-300">
                                {rec.candidate_identifier}
                                {rec.candidate_survey_number && (
                                  <span className="text-[10px] text-slate-500 ml-1.5">
                                    ({rec.candidate_survey_number})
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-2">
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                    rec.geometry_status === 'CONGRUENT'
                                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                      : rec.geometry_status === 'BOUNDARY_VARIANCE_RECONCILED'
                                      ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                                      : 'bg-purple-950 text-purple-300 border border-purple-800'
                                  }`}
                                >
                                  {rec.geometry_status}
                                </span>
                              </td>
                              <td className="px-4 py-2 text-right">
                                <div>{rec.harmonized_area.toLocaleString()} m²</div>
                                {rec.area_discrepancy_pct > 0 && (
                                  <div
                                    className={`text-[10px] ${
                                      rec.area_discrepancy_pct > areaTolerancePct
                                        ? 'text-amber-400 font-semibold'
                                        : 'text-slate-500'
                                    }`}
                                  >
                                    Δ {rec.area_discrepancy_pct}%
                                  </div>
                                )}
                              </td>
                              <td className="px-4 py-2">
                                <span className="font-semibold text-slate-200">
                                  {rec.harmonized_land_use || 'N/A'}
                                </span>
                                {rec.source_land_use !== rec.candidate_land_use && (
                                  <div className="text-[9px] text-slate-500">
                                    (from {rec.candidate_land_use || rec.source_land_use})
                                  </div>
                                )}
                              </td>
                              <td className="px-4 py-2">
                                <span className="px-1.5 py-0.5 rounded text-[10px] bg-surface-900 border border-border text-slate-300">
                                  {rec.harmonized_mutation_status || 'N/A'}
                                </span>
                              </td>
                              <td className="px-4 py-2">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                    rec.harmonized_risk_level === 'High'
                                      ? 'bg-rose-950 text-rose-300 border border-rose-800'
                                      : rec.harmonized_risk_level === 'Medium'
                                      ? 'bg-amber-950 text-amber-300 border border-amber-800'
                                      : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                  }`}
                                >
                                  {rec.harmonized_risk_level || 'Low'}
                                </span>
                              </td>
                              <td className="px-4 py-2 text-center">
                                {rec.has_conflicts ? (
                                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950/80 text-amber-300 border border-amber-700">
                                    {rec.conflict_count} Conflicts
                                  </span>
                                ) : (
                                  <span className="text-emerald-400 text-[10px]">Zero Conflicts</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGES 08–14: DOWNSTREAM HARMONIZATION PIPELINE           */}
        {/* ========================================================= */}
        {stage.stage_number > 7 && (
          <div className="space-y-4">
            <div className="p-5 rounded-lg bg-surface-950/80 border border-border space-y-3">
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-mono uppercase tracking-wider text-slate-200 font-semibold">
                  Stage Overview &amp; Requirements
                </h3>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                {stage.description}
              </p>

              <div className="p-3 rounded bg-surface-900 border border-border text-xs font-mono text-slate-300 space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">Prerequisites Status:</span>
                  {stage.prerequisites_met ? (
                    <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Ready for downstream execution
                    </span>
                  ) : (
                    <span className="text-amber-400 flex items-center gap-1">
                      <Lock className="w-3.5 h-3.5" />
                      {stage.prerequisites_message || 'Pending upstream stages'}
                    </span>
                  )}
                </div>
                {stage.stage_number === 8 && stage.prerequisites_met && (
                  <div className="pt-2 text-xs text-cyan-300">
                    Stage 07 has forwarded attribute and geometry discrepancies ready for detection in Stage 08.
                  </div>
                )}
                {stage.stage_number === 11 && (
                  <div className="pt-2">
                    <Link
                      to={`/projects/${projectId}/reconciliation`}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-700 text-cyan-300 text-xs font-mono transition-colors"
                    >
                      <span>Access Interactive Review Interface</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                )}
                {stage.stage_number === 12 && (
                  <div className="pt-2">
                    <Link
                      to={`/projects/${projectId}/unified-records`}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-700 text-emerald-300 text-xs font-mono transition-colors"
                    >
                      <span>View Unified Land Records (ULR)</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
