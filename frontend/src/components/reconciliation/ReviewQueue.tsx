import React from 'react'
import {
  Scale,
  AlertTriangle,
  HelpCircle,
  CheckCircle2,
  XCircle,
  Flag,
  Clock,
  Layers,
  Search,
  Filter,
  ArrowRight,
  ShieldCheck,
  ChevronRight,
  Sparkles,
} from 'lucide-react'
import { useReviewQueue } from '../../hooks/useMatching'
import type { ReviewQueueCategory, ReviewQueueItem, ReviewStatus, CandidateRole } from '../../types'

interface ReviewQueueProps {
  runId: string
  selectedMatchId: string | null
  onSelectMatch: (matchId: string) => void
  activeCategory: ReviewQueueCategory
  onChangeCategory: (category: ReviewQueueCategory) => void
}

export const ReviewQueue: React.FC<ReviewQueueProps> = ({
  runId,
  selectedMatchId,
  onSelectMatch,
  activeCategory,
  onChangeCategory,
}) => {
  const { data: queueData, isLoading } = useReviewQueue(runId, {
    category: activeCategory,
  })

  const items = queueData?.items || []
  const counts = queueData?.category_counts || {
    all: 0,
    pending: 0,
    ambiguous: 0,
    conflict: 0,
    possible: 0,
    reviewed: 0,
    accepted: 0,
    rejected: 0,
    flagged: 0,
  }

  const tabs: { key: ReviewQueueCategory; label: string; count: number; icon: React.ReactNode }[] = [
    {
      key: 'pending',
      label: 'Pending',
      count: counts.pending,
      icon: <Clock className="w-3 h-3 text-amber-400" />,
    },
    {
      key: 'ambiguous',
      label: 'Ambiguous',
      count: counts.ambiguous,
      icon: <Scale className="w-3 h-3 text-amber-400" />,
    },
    {
      key: 'conflict',
      label: 'Conflict',
      count: counts.conflict,
      icon: <AlertTriangle className="w-3 h-3 text-red-400" />,
    },
    {
      key: 'possible',
      label: 'Possible',
      count: counts.possible,
      icon: <HelpCircle className="w-3 h-3 text-blue-400" />,
    },
    {
      key: 'accepted',
      label: 'Accepted',
      count: counts.accepted,
      icon: <CheckCircle2 className="w-3 h-3 text-emerald-400" />,
    },
    {
      key: 'rejected',
      label: 'Rejected',
      count: counts.rejected,
      icon: <XCircle className="w-3 h-3 text-rose-400" />,
    },
    {
      key: 'flagged',
      label: 'Flagged',
      count: counts.flagged,
      icon: <Flag className="w-3 h-3 text-orange-400" />,
    },
    {
      key: 'reviewed',
      label: 'Reviewed',
      count: counts.reviewed,
      icon: <ShieldCheck className="w-3 h-3 text-cyan-400" />,
    },
    {
      key: 'all',
      label: 'All Candidates',
      count: counts.all,
      icon: <Layers className="w-3 h-3 text-slate-400" />,
    },
  ]

  const getPriorityBadge = (priority: string, role?: CandidateRole | null) => {
    switch (priority) {
      case 'AMBIGUOUS':
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-950/80 text-amber-300 border border-amber-700/60">
            <Scale className="w-2.5 h-2.5 text-amber-400" />
            Ambiguous
          </span>
        )
      case 'CONFLICT':
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-red-950/80 text-red-300 border border-red-700/60">
            <AlertTriangle className="w-2.5 h-2.5 text-red-400" />
            Conflict
          </span>
        )
      case 'POSSIBLE':
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-blue-950/80 text-blue-300 border border-blue-700/60">
            <HelpCircle className="w-2.5 h-2.5 text-blue-400" />
            Possible
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-surface-800 text-slate-400 border border-border">
            {role || 'Other'}
          </span>
        )
    }
  }

  const getReviewBadge = (status: ReviewStatus) => {
    switch (status) {
      case 'ACCEPTED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-950/90 text-emerald-300 border border-emerald-600 shadow-sm">
            <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400" />
            Accepted
          </span>
        )
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-rose-950/90 text-rose-300 border border-rose-600 shadow-sm">
            <XCircle className="w-2.5 h-2.5 text-rose-400" />
            Rejected
          </span>
        )
      case 'FLAGGED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-orange-950/90 text-orange-300 border border-orange-600 shadow-sm">
            <Flag className="w-2.5 h-2.5 text-orange-400" />
            Flagged
          </span>
        )
      case 'PENDING':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-surface-800 text-amber-300/90 border border-amber-600/40">
            <Clock className="w-2.5 h-2.5 text-amber-400" />
            Pending Review
          </span>
        )
    }
  }

  return (
    <div className="h-full flex flex-col bg-surface-900 border-t border-border font-mono text-slate-200 select-none">
      {/* Category Filter Tabs */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-950 border-b border-border overflow-x-auto gap-2 flex-shrink-0">
        <div className="flex items-center gap-1">
          {tabs.map((tab) => {
            const isActive = activeCategory === tab.key
            return (
              <button
                key={tab.key}
                onClick={() => onChangeCategory(tab.key)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-medium transition-all ${
                  isActive
                    ? 'bg-cyan-950/80 text-cyan-200 border border-cyan-600 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-surface-850 border border-transparent'
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
                <span
                  className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
                    isActive
                      ? 'bg-cyan-900/60 text-cyan-200'
                      : 'bg-surface-800 text-slate-400'
                  }`}
                >
                  {tab.count}
                </span>
              </button>
            )
          })}
        </div>

        <div className="text-[10px] text-slate-500 whitespace-nowrap pl-2">
          Prioritized by: <strong className="text-slate-400">Category & Machine Score</strong>
        </div>
      </div>

      {/* Queue Items Table / List */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center p-8 text-slate-400 text-xs gap-2">
            <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
            <span>Loading prioritized review queue...</span>
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-center text-slate-500 text-xs">
            <CheckCircle2 className="w-8 h-8 text-emerald-500 mb-2 opacity-60" />
            <p className="font-semibold text-slate-300 mb-1">Queue Clear for this Filter</p>
            <p className="text-[11px] text-slate-500 max-w-sm">
              No candidates found matching the selected category ({activeCategory.toUpperCase()}). Switch filters above or run a new matching analysis.
            </p>
          </div>
        ) : (
          <table className="w-full text-left border-collapse text-xs">
            <thead className="bg-surface-950/90 text-slate-400 text-[10px] uppercase font-bold sticky top-0 z-10 border-b border-border">
              <tr>
                <th className="py-2 px-3 w-10 text-center">#</th>
                <th className="py-2 px-3 w-32">Priority</th>
                <th className="py-2 px-3">Source Feature</th>
                <th className="py-2 px-3">Candidate Feature</th>
                <th className="py-2 px-3 w-28">Machine Score</th>
                <th className="py-2 px-3">Primary Signal / Reason</th>
                <th className="py-2 px-3 w-36 text-center">Human Review</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {items.map((item: ReviewQueueItem, idx: number) => {
                const isSelected = item.id === selectedMatchId
                const scorePct = Math.round(item.overall_score * 100)

                return (
                  <tr
                    key={item.id}
                    onClick={() => onSelectMatch(item.id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-cyan-950/60 border-l-4 border-l-cyan-400 text-cyan-50'
                        : 'hover:bg-surface-850/70 text-slate-300'
                    }`}
                  >
                    {/* Index */}
                    <td className="py-2 px-3 text-center text-[10px] text-slate-500 font-mono">
                      {idx + 1}
                    </td>

                    {/* Priority badge */}
                    <td className="py-2 px-3">
                      {getPriorityBadge(item.priority_category, item.candidate_role)}
                    </td>

                    {/* Source Feature */}
                    <td className="py-2 px-3">
                      <div className="font-bold text-cyan-300 truncate max-w-[160px]">
                        {item.source_identifier}
                      </div>
                      <div className="text-[10px] text-slate-400 truncate max-w-[160px]">
                        {item.source_dataset_name} ({item.source_geometry_type})
                      </div>
                    </td>

                    {/* Candidate Feature */}
                    <td className="py-2 px-3">
                      {item.candidate_identifier ? (
                        <>
                          <div className="font-bold text-amber-300 truncate max-w-[160px]">
                            {item.candidate_identifier}
                          </div>
                          <div className="text-[10px] text-slate-400 truncate max-w-[160px]">
                            {item.candidate_dataset_name || 'Candidate Dataset'} ({item.candidate_geometry_type || 'geom'})
                          </div>
                        </>
                      ) : (
                        <span className="text-slate-500 italic">No candidate</span>
                      )}
                    </td>

                    {/* Machine Score */}
                    <td className="py-2 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-10 text-right font-bold font-mono">
                          {scorePct}%
                        </div>
                        <div className="flex-1 h-1.5 bg-surface-800 rounded-full overflow-hidden max-w-[48px]">
                          <div
                            className={`h-full rounded-full ${
                              scorePct >= 80
                                ? 'bg-emerald-400'
                                : scorePct >= 65
                                ? 'bg-amber-400'
                                : scorePct >= 50
                                ? 'bg-orange-500'
                                : 'bg-red-500'
                            }`}
                            style={{ width: `${scorePct}%` }}
                          />
                        </div>
                      </div>
                      {item.score_gap !== null && item.score_gap !== undefined && (
                        <div className="text-[9px] text-slate-400 font-mono">
                          Gap: +{Math.round(item.score_gap * 100)}%
                        </div>
                      )}
                    </td>

                    {/* Primary Reason */}
                    <td className="py-2 px-3">
                      <div className="text-[11px] text-slate-300 truncate max-w-[280px]">
                        {item.primary_reason || 'Candidate generated via spatial proximity analysis'}
                      </div>
                      {item.latest_review_comment && (
                        <div className="text-[10px] text-cyan-400/90 italic truncate max-w-[280px]">
                          Note: "{item.latest_review_comment}"
                        </div>
                      )}
                    </td>

                    {/* Review Decision Status */}
                    <td className="py-2 px-3 text-center">
                      {getReviewBadge(item.review_status)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
