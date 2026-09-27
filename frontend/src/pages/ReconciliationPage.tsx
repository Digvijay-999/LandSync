import React, { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  Play,
  Layers,
  History,
  CheckCircle2,
  XCircle,
  Flag,
  Clock,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  Sparkles,
  Loader2,
  RefreshCw,
  Sliders,
  Database,
  Star,
  Scale,
  Award,
  ListOrdered,
  Table,
  FlaskConical,
  ShieldCheck,
} from 'lucide-react'
import { useProject } from '../hooks/useProjects'
import { useProjectDatasets } from '../hooks/useDatasets'
import {
  useMatchingRuns,
  useMatchingRun,
  useRunMatches,
  useMatchDetail,
  useReviewStatistics,
  useSeedDemoReviews,
} from '../hooks/useMatching'
import type { MatchRun, ReviewQueueCategory } from '../types'
import { MatchRunModal } from '../components/reconciliation/MatchRunModal'
import { MatchResultsTable } from '../components/reconciliation/MatchResultsTable'
import { ReviewQueue } from '../components/reconciliation/ReviewQueue'
import { MatchDetailPanel } from '../components/reconciliation/MatchDetailPanel'
import { ReconciliationMap } from '../components/reconciliation/ReconciliationMap'

export const ReconciliationPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const safeProjectId = projectId || ''

  const { data: project, isLoading: projectLoading } = useProject(safeProjectId)
  const { data: datasetsData } = useProjectDatasets(safeProjectId)
  const datasets = datasetsData?.items || []

  // Matching Runs Query
  const {
    data: runsData,
    isLoading: runsLoading,
    refetch: refetchRuns,
  } = useMatchingRuns(safeProjectId)
  const runs = runsData?.items || []

  // Active Selected Run
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  // Default to latest run when runs load
  useEffect(() => {
    if (!selectedRunId && runs.length > 0) {
      setSelectedRunId(runs[0].id)
    }
  }, [runs, selectedRunId])

  // Active Selected Run Details
  const { data: activeRun, isLoading: runDetailLoading } = useMatchingRun(
    selectedRunId || undefined
  )

  // Review Statistics for Active Run
  const {
    data: reviewStats,
    isLoading: reviewStatsLoading,
    refetch: refetchStats,
  } = useReviewStatistics(selectedRunId || undefined)

  // Matches for Active Run (Used for All Matches Table view)
  const {
    data: matchesData,
    isLoading: matchesLoading,
    refetch: refetchMatches,
  } = useRunMatches(selectedRunId || undefined)
  const matches = matchesData?.items || []

  // Active Selected Match (for details and map highlighting)
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null)

  // View Mode: 'queue' (Review Queue) or 'table' (All Matches Table)
  const [viewMode, setViewMode] = useState<'queue' | 'table'>('queue')

  // Review Queue Category Filter
  const [reviewCategory, setReviewCategory] = useState<ReviewQueueCategory>('pending')

  // Clear or auto-select first match when active run changes
  useEffect(() => {
    if (matches.length > 0 && !selectedMatchId) {
      setSelectedMatchId(matches[0].id)
    }
  }, [selectedRunId, matches.length, selectedMatchId])

  // Detailed Match Data Query
  const { data: matchDetail, isLoading: matchDetailLoading } = useMatchDetail(
    selectedMatchId || undefined
  )

  // Seed Demo Reviews Mutation
  const seedDemoMutation = useSeedDemoReviews(selectedRunId || undefined)

  // Modal State
  const [isRunModalOpen, setIsRunModalOpen] = useState(false)

  const handleRunSuccess = (newRunId: string) => {
    setSelectedRunId(newRunId)
    refetchRuns()
  }

  const handleRefreshAll = () => {
    refetchRuns()
    refetchMatches()
    refetchStats()
  }

  if (projectLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] text-slate-400 font-mono">
        <Loader2 className="w-8 h-8 animate-spin text-cyan-400 mb-2" />
        <span>Loading reconciliation workspace...</span>
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
              <span className="text-xs uppercase tracking-wider text-cyan-400 font-bold">
                Reconciliation Workspace
              </span>
              <span className="text-slate-600">/</span>
              <span className="text-xs font-semibold text-slate-200">{project.name}</span>
            </div>
            <div className="text-[10px] text-slate-400 flex items-center gap-2">
              <span>Canonical CRS: <strong className="text-cyan-300">{project.target_crs}</strong></span>
              <span className="text-slate-600">•</span>
              <span>{runs.length} Runs Recorded</span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5">
          {/* View Mode Toggle: Review Queue vs All Matches */}
          <div className="flex items-center bg-surface-950 border border-border rounded p-0.5 text-xs">
            <button
              onClick={() => setViewMode('queue')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-bold transition-all ${
                viewMode === 'queue'
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-700/80 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Prioritized Human Review Queue"
            >
              <ListOrdered className="w-3.5 h-3.5" />
              <span>Review Queue</span>
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-bold transition-all ${
                viewMode === 'table'
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-700/80 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="All Matches Data Table"
            >
              <Table className="w-3.5 h-3.5" />
              <span>All Matches</span>
            </button>
          </div>

          {/* Seed Demo Reviews Button */}
          {selectedRunId && (
            <button
              onClick={() => seedDemoMutation.mutate()}
              disabled={seedDemoMutation.isPending}
              title="Seed deterministic demo decisions (1 Accepted, 1 Rejected, 1 Flagged) for review demonstration"
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-surface-850 hover:bg-surface-800 border border-border text-amber-300 hover:text-amber-200 text-xs font-semibold transition-all disabled:opacity-50"
            >
              {seedDemoMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FlaskConical className="w-3.5 h-3.5 text-amber-400" />
              )}
              <span className="hidden sm:inline">Seed Demo</span>
            </button>
          )}

          <Link
            to={`/projects/${safeProjectId}/unified-records`}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-surface-850 hover:bg-surface-800 border border-emerald-700/80 text-emerald-300 hover:text-emerald-200 text-xs font-semibold transition-all"
            title="Go to Unified Land Records"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span className="hidden sm:inline">Unified Records</span>
          </Link>

          <button
            onClick={handleRefreshAll}
            title="Refresh runs and statistics"
            className="p-1.5 rounded bg-surface-850 hover:bg-surface-800 border border-border text-slate-400 hover:text-slate-200 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setIsRunModalOpen(true)}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded bg-cyan-500 hover:bg-cyan-400 text-surface-950 font-bold text-xs shadow-md transition-all active:scale-[0.98]"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>New Matching Run</span>
          </button>
        </div>
      </div>

      {/* 2. Run Metric Summary Banner (Review Statistics & Machine Quality Metrics) */}
      {activeRun && (
        <div className="h-10 bg-surface-950 border-b border-border px-4 flex items-center justify-between text-xs flex-shrink-0">
          <div className="flex items-center gap-5 overflow-x-auto py-1">
            {/* Active Run ID */}
            <div className="flex items-center gap-2">
              <span className="text-slate-500 text-[10px] uppercase font-bold">Run:</span>
              <span className="px-2 py-0.5 rounded bg-surface-850 text-cyan-300 font-mono text-[11px] border border-border">
                {activeRun.id.substring(0, 8)}...
              </span>
            </div>

            {/* Live Review Statistics (Direct from Database) */}
            <div className="flex items-center gap-4 pl-2 border-l border-border/80">
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400 text-[10px] uppercase font-bold">Candidates:</span>
                <span className="font-bold text-slate-200 font-mono">
                  {reviewStats?.total_candidates ?? activeRun.total_candidates}
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-amber-400 text-[10px] uppercase font-bold">Pending:</span>
                <span className="font-bold text-amber-300 font-mono">
                  {reviewStats?.pending_review ?? 0}
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400 text-[10px] uppercase font-bold">Accepted:</span>
                <span className="font-bold text-emerald-300 font-mono">
                  {reviewStats?.accepted ?? 0}
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                <XCircle className="w-3.5 h-3.5 text-rose-400" />
                <span className="text-rose-400 text-[10px] uppercase font-bold">Rejected:</span>
                <span className="font-bold text-rose-300 font-mono">
                  {reviewStats?.rejected ?? 0}
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                <Flag className="w-3.5 h-3.5 text-orange-400" />
                <span className="text-orange-400 text-[10px] uppercase font-bold">Flagged:</span>
                <span className="font-bold text-orange-300 font-mono">
                  {reviewStats?.flagged ?? 0}
                </span>
              </div>
            </div>

            {/* Quality Breakdown separator */}
            {activeRun.quality_metrics && (
              <div className="hidden xl:flex items-center gap-3 pl-3 border-l border-border/80">
                <div className="flex items-center gap-1">
                  <Star className="w-3 h-3 text-emerald-400" />
                  <span className="text-[10px] text-slate-400">Unambiguous:</span>
                  <span className="text-emerald-300 font-bold">{activeRun.quality_metrics.features_with_unambiguous_best}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Scale className="w-3 h-3 text-amber-400" />
                  <span className="text-[10px] text-slate-400">Ambiguous:</span>
                  <span className="text-amber-300 font-bold">{activeRun.quality_metrics.features_with_ambiguous_best}</span>
                </div>
              </div>
            )}
          </div>

          <div className="hidden lg:flex items-center gap-2 text-[10px] text-slate-500">
            <span>Radius: {activeRun.configuration?.candidate_search_distance_meters || 50}m</span>
            <span>•</span>
            <span>Tie Tol: {activeRun.configuration?.best_candidate_tie_tolerance ?? 0.015}</span>
            <span>•</span>
            <span>Ver: {activeRun.configuration?.scoring_version || '1.1'}</span>
          </div>
        </div>
      )}

      {/* 3. Main Workspace Body (3-panel: Left Runs List, Center Map & Queue/Table, Right Match Detail) */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Column: Runs History Selector */}
        <div className="w-60 bg-surface-900 border-r border-border flex flex-col flex-shrink-0 select-none">
          <div className="p-3 border-b border-border bg-surface-950/80 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-slate-300 text-xs font-bold uppercase tracking-wider">
              <History className="w-3.5 h-3.5 text-cyan-400" />
              <span>Matching Runs</span>
            </div>
            <span className="px-1.5 py-0.5 rounded bg-surface-850 text-slate-400 text-[10px]">
              {runs.length}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {runsLoading ? (
              <div className="p-4 text-center text-slate-500 text-xs flex items-center justify-center gap-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                <span>Loading runs...</span>
              </div>
            ) : runs.length === 0 ? (
              <div className="p-4 text-center text-slate-500 text-xs space-y-2">
                <p>No matching runs yet.</p>
                <p className="text-[10px] text-slate-600">
                  Click "New Matching Run" to execute candidate generation and cross-dataset reconciliation.
                </p>
              </div>
            ) : (
              runs.map((r: MatchRun, idx: number) => {
                const isSelected = r.id === selectedRunId
                const dateStr = new Date(r.created_at).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })
                const dateFull = new Date(r.created_at).toLocaleDateString()

                return (
                  <button
                    key={r.id}
                    onClick={() => setSelectedRunId(r.id)}
                    className={`w-full text-left p-2.5 rounded-lg border transition-all ${
                      isSelected
                        ? 'bg-cyan-950/50 border-cyan-700/80 text-cyan-100 shadow-sm'
                        : 'bg-surface-950/50 border-border hover:bg-surface-850 text-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between text-[11px] mb-1">
                      <span className="font-bold text-slate-200">
                        Run #{runs.length - idx}
                      </span>
                      <span className="text-[10px] text-slate-500">{dateStr}</span>
                    </div>

                    <div className="text-[10px] text-slate-400 flex items-center justify-between">
                      <span className="text-emerald-400 font-semibold">
                        {r.quality_metrics ? `${r.quality_metrics.features_with_unambiguous_best} Best` : `${r.total_matches} Matched`}
                      </span>
                      {r.quality_metrics?.features_with_ambiguous_best ? (
                        <span className="text-amber-400 font-semibold">
                          {r.quality_metrics.features_with_ambiguous_best} Amb.
                        </span>
                      ) : (
                        <span className="text-red-400 font-semibold">
                          {r.total_conflicts} Conf.
                        </span>
                      )}
                      <span className="text-slate-400">
                        {r.quality_metrics?.features_with_no_candidates ?? r.total_unmatched} Unm.
                      </span>
                    </div>

                    <div className="mt-1.5 pt-1.5 border-t border-border/50 text-[9px] text-slate-500 flex justify-between">
                      <span>{dateFull}</span>
                      <span className="uppercase text-slate-400">{r.status}</span>
                    </div>
                  </button>
                )
              })
            )}
          </div>
        </div>

        {/* Center Column: Map & Review Queue / Matches Table */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Top Half: Interactive MapLibre Map */}
          <div className="flex-1 min-h-[340px] relative">
            <ReconciliationMap
              projectId={safeProjectId}
              targetCrs={project.target_crs}
              selectedMatch={matchDetail || null}
            />
          </div>

          {/* Bottom Half: Prioritized Review Queue or Results Table */}
          <div className="h-72 flex-shrink-0">
            {viewMode === 'queue' && selectedRunId ? (
              <ReviewQueue
                runId={selectedRunId}
                selectedMatchId={selectedMatchId}
                onSelectMatch={(id) => setSelectedMatchId(id)}
                activeCategory={reviewCategory}
                onChangeCategory={setReviewCategory}
              />
            ) : (
              <MatchResultsTable
                matches={matches}
                selectedMatchId={selectedMatchId}
                onSelectMatch={(id) => setSelectedMatchId(id)}
                isLoading={matchesLoading}
              />
            )}
          </div>
        </div>

        {/* Right Column: Explainable Match Detail & Human Review Action Panel */}
        <MatchDetailPanel
          matchDetail={matchDetail || null}
          isLoading={matchDetailLoading}
          onClose={() => setSelectedMatchId(null)}
          onSelectMatch={(id) => setSelectedMatchId(id)}
        />
      </div>

      {/* Matching Run Modal */}
      <MatchRunModal
        projectId={safeProjectId}
        datasets={datasets}
        isOpen={isRunModalOpen}
        onClose={() => setIsRunModalOpen(false)}
        onRunSuccess={handleRunSuccess}
      />
    </div>
  )
}
