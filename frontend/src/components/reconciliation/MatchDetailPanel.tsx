import React, { useState } from 'react'
import {
  X,
  Target,
  CheckCircle2,
  XCircle,
  Flag,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  Layers,
  ArrowRight,
  Sparkles,
  Star,
  Scale,
  Award,
  ChevronRight,
  Clock,
  History,
  MessageSquare,
  ShieldCheck,
  Send,
  Loader2,
} from 'lucide-react'
import type {
  MatchDetailResponse,
  MatchStatus,
  CandidateRole,
  ReviewDecision,
  ReviewStatus,
} from '../../types'
import {
  useSourceFeatureCandidates,
  useSubmitMatchReview,
} from '../../hooks/useMatching'

interface MatchDetailPanelProps {
  matchDetail: MatchDetailResponse | null
  isLoading: boolean
  onClose: () => void
  onSelectMatch?: (matchId: string) => void
}

export const MatchDetailPanel: React.FC<MatchDetailPanelProps> = ({
  matchDetail,
  isLoading,
  onClose,
  onSelectMatch,
}) => {
  const [commentText, setCommentText] = useState('')

  const sourceFeatureId =
    matchDetail?.source_feature?.source_feature_id || matchDetail?.source_feature?.id

  const { data: siblingCandidates, isLoading: siblingLoading } = useSourceFeatureCandidates(
    matchDetail?.match_run_id,
    sourceFeatureId
  )

  const reviewMutation = useSubmitMatchReview(matchDetail?.id, matchDetail?.match_run_id)

  const handleReviewAction = async (decision: ReviewDecision) => {
    if (!matchDetail) return
    await reviewMutation.mutateAsync({
      decision,
      comment: commentText.trim() ? commentText.trim() : null,
    })
    setCommentText('')
  }

  if (isLoading) {
    return (
      <div className="w-96 lg:w-[420px] bg-surface-900 border-l border-border flex flex-col items-center justify-center p-8 text-slate-400 font-mono text-xs flex-shrink-0">
        <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mb-3" />
        <span>Loading match breakdown...</span>
      </div>
    )
  }

  if (!matchDetail) {
    return (
      <div className="w-96 lg:w-[420px] bg-surface-900 border-l border-border flex flex-col items-center justify-center p-8 text-center text-slate-500 font-mono text-xs select-none flex-shrink-0">
        <Target className="w-8 h-8 text-slate-600 mb-3" />
        <p className="font-semibold text-slate-400 mb-1">No Feature Match Selected</p>
        <p className="text-[11px] leading-relaxed">
          Select a candidate relationship from the review queue or table to inspect multi-signal scoring, side-by-side data comparison, and record human decisions.
        </p>
      </div>
    )
  }

  const {
    id: currentMatchId,
    status,
    review_status,
    rank,
    is_best_candidate,
    candidate_role,
    score_gap,
    candidate_count,
    overall_score,
    explanation,
    source_feature,
    candidate_feature,
    scoring_version,
    reviews = [],
    created_at,
  } = matchDetail

  const getStatusBadge = (st: MatchStatus) => {
    switch (st) {
      case 'matched':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-950/80 text-emerald-300 border border-emerald-700/60 shadow-sm">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Matched
          </span>
        )
      case 'possible_match':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-950/80 text-amber-300 border border-amber-700/60 shadow-sm">
            <HelpCircle className="w-3.5 h-3.5" />
            Possible
          </span>
        )
      case 'conflict':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-red-950/80 text-red-300 border border-red-700/60 shadow-sm">
            <AlertTriangle className="w-3.5 h-3.5" />
            Conflict
          </span>
        )
      case 'unmatched':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700 shadow-sm">
            <AlertCircle className="w-3.5 h-3.5" />
            Unmatched
          </span>
        )
    }
  }

  const getReviewStatusBadge = (rStatus: ReviewStatus) => {
    switch (rStatus) {
      case 'ACCEPTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-950 text-emerald-300 border border-emerald-500 shadow-sm">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            Accepted
          </span>
        )
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-rose-950 text-rose-300 border border-rose-500 shadow-sm">
            <XCircle className="w-3.5 h-3.5 text-rose-400" />
            Rejected
          </span>
        )
      case 'FLAGGED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-orange-950 text-orange-300 border border-orange-500 shadow-sm">
            <Flag className="w-3.5 h-3.5 text-orange-400" />
            Flagged
          </span>
        )
      case 'PENDING':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-surface-800 text-amber-300 border border-amber-600/50 shadow-sm">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            Pending Review
          </span>
        )
    }
  }

  const getRoleHeaderBadge = (role?: CandidateRole | null, rk?: number | null) => {
    switch (role) {
      case 'BEST':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-950/90 text-emerald-300 border border-emerald-700 shadow-sm">
            <Star className="w-3.5 h-3.5 text-emerald-400 fill-emerald-400" />
            ★ BEST CANDIDATE (Rank #{rk || 1})
          </span>
        )
      case 'AMBIGUOUS':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-950/90 text-amber-300 border border-amber-700 shadow-sm">
            <Scale className="w-3.5 h-3.5 text-amber-400" />
            AMBIGUOUS (Rank #{rk || 1})
          </span>
        )
      case 'SECONDARY':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
            SECONDARY (Rank #{rk || 2})
          </span>
        )
      case 'CONFLICT':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-red-950/90 text-red-300 border border-red-700">
            <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
            CONFLICT (Rank #{rk || 1})
          </span>
        )
      case 'UNMATCHED':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-surface-800 text-slate-400 border border-border">
            UNMATCHED
          </span>
        )
    }
  }

  const scorePct = Math.round(overall_score * 100)

  // Signals data for bar visualization
  const signals = [
    {
      name: 'Spatial Overlap',
      key: 'spatial_overlap',
      score: explanation.component_scores.spatial_overlap,
      desc: 'Intersection / Union (IoU) polygon footprint overlap',
    },
    {
      name: 'Centroid Similarity',
      key: 'centroid_similarity',
      score: explanation.component_scores.centroid_similarity,
      desc: 'Proximity of real-world centroids (Haversine distance)',
    },
    {
      name: 'Area Similarity',
      key: 'area_similarity',
      score: explanation.component_scores.area_similarity,
      desc: 'Ratio of smaller to larger polygon surface area',
    },
    {
      name: 'Geometry Similarity',
      key: 'geometry_similarity',
      score: explanation.component_scores.geometry_similarity,
      desc: 'Structural contour alignment & shape index',
    },
    {
      name: 'Attribute Similarity',
      key: 'attribute_similarity',
      score: explanation.component_scores.attribute_similarity,
      desc: 'Fuzzy / token overlap across identifier & name fields',
    },
  ]

  // Side-by-Side Comparison Properties Builder
  const sourceProps = source_feature?.properties || {}
  const candProps = candidate_feature?.properties || {}
  const allPropertyKeys = Array.from(
    new Set([
      ...Object.keys(sourceProps).filter((k) => !k.startsWith('_')),
      ...Object.keys(candProps).filter((k) => !k.startsWith('_')),
    ])
  ).sort()

  return (
    <div className="w-96 lg:w-[420px] bg-surface-900 border-l border-border flex flex-col h-full font-mono text-xs overflow-hidden select-none flex-shrink-0">
      {/* Panel Header */}
      <div className="p-3.5 border-b border-border bg-surface-950/80 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-cyan-400" />
          <span className="font-bold text-slate-200 uppercase tracking-wider text-xs">
            Match Review & Reconciliation
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500 font-mono">v{scoring_version}</span>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-800 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Dual Status Card: Machine Result vs Human Decision */}
        <div className="p-3.5 rounded-lg bg-surface-950 border border-border shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-border/50 pb-2">
            <div>
              <span className="text-[9px] text-slate-500 uppercase tracking-wider block font-bold mb-1">
                Machine Result
              </span>
              {getStatusBadge(status)}
            </div>
            <div className="text-right">
              <span className="text-[9px] text-slate-500 uppercase tracking-wider block font-bold mb-0.5">
                Machine Confidence
              </span>
              <div className="text-2xl font-black font-mono tracking-tight text-cyan-400">
                {scorePct}%
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-0.5">
            <div>
              <span className="text-[9px] text-slate-500 uppercase tracking-wider block font-bold mb-1">
                Human Review Status
              </span>
              {getReviewStatusBadge(review_status)}
            </div>
            <div className="text-right">
              <span className="text-[9px] text-slate-500 uppercase tracking-wider block font-bold mb-1">
                Candidate Role
              </span>
              {getRoleHeaderBadge(candidate_role, rank)}
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* HUMAN REVIEW DECISION CONTROLS (Accept / Reject / Flag + Comment) */}
        {/* ========================================================================= */}
        <div className="rounded-lg bg-surface-950 border border-cyan-900/50 p-3.5 space-y-3 shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
              Human Decision Action
            </span>
            {reviewMutation.isPending && (
              <span className="text-[10px] text-cyan-400 flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" /> Recording...
              </span>
            )}
          </div>

          {/* Comment Input */}
          <div>
            <textarea
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              placeholder="Optional reviewer note (e.g. 'Boundary alignment confirmed via drone survey')..."
              rows={2}
              maxLength={2000}
              className="w-full bg-surface-900 border border-border rounded p-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 resize-none font-sans"
            />
          </div>

          {/* Action Buttons: ACCEPT, REJECT, FLAG */}
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={() => handleReviewAction('ACCEPTED')}
              disabled={reviewMutation.isPending}
              className="flex items-center justify-center gap-1.5 px-2.5 py-2 rounded bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] text-white font-bold text-[11px] shadow transition-all disabled:opacity-50"
              title="Accept this candidate match relationship"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>ACCEPT</span>
            </button>

            <button
              onClick={() => handleReviewAction('REJECTED')}
              disabled={reviewMutation.isPending}
              className="flex items-center justify-center gap-1.5 px-2.5 py-2 rounded bg-rose-700 hover:bg-rose-600 active:scale-[0.98] text-white font-bold text-[11px] shadow transition-all disabled:opacity-50"
              title="Reject this candidate match"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>REJECT</span>
            </button>

            <button
              onClick={() => handleReviewAction('FLAGGED')}
              disabled={reviewMutation.isPending}
              className="flex items-center justify-center gap-1.5 px-2.5 py-2 rounded bg-amber-600 hover:bg-amber-500 active:scale-[0.98] text-white font-bold text-[11px] shadow transition-all disabled:opacity-50"
              title="Flag relationship for further investigation"
            >
              <Flag className="w-3.5 h-3.5" />
              <span>FLAG</span>
            </button>
          </div>
          <div className="text-[9px] text-slate-500 text-center">
            Decisions are auditable. Machine score and classification will NOT be overwritten.
          </div>
        </div>

        {/* Ambiguity Warning Banner if applicable */}
        {candidate_role === 'AMBIGUOUS' && (
          <div className="p-2.5 rounded bg-amber-950/70 border border-amber-800 text-amber-200 text-[11px] leading-relaxed">
            <div className="flex items-start gap-1.5 font-semibold text-amber-300 mb-1">
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-amber-400" />
              <span>Ambiguous Match (Tie Detected)</span>
            </div>
            Top candidates scored within tie tolerance (0.015). A human decision is recommended to designate the valid parcel match.
          </div>
        )}

        {/* ========================================================================= */}
        {/* SIDE-BY-SIDE DATA COMPARISON (Requirement 7) */}
        {/* ========================================================================= */}
        <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-cyan-400" />
              Side-by-Side Data Comparison
            </span>
            <span className="text-[10px] text-slate-500">
              {allPropertyKeys.length} Attributes
            </span>
          </div>

          <div className="border border-border/80 rounded overflow-hidden">
            <table className="w-full text-left border-collapse text-[10px]">
              <thead className="bg-surface-900 text-slate-400 border-b border-border/80 uppercase font-bold">
                <tr>
                  <th className="p-1.5 w-1/3">Attribute</th>
                  <th className="p-1.5 w-1/3 text-cyan-300">
                    Source: {source_feature.dataset_name || 'Source'}
                  </th>
                  <th className="p-1.5 w-1/3 text-amber-300">
                    Candidate: {candidate_feature?.dataset_name || 'Candidate'}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40 font-mono">
                {allPropertyKeys.map((key) => {
                  const valSrc = sourceProps[key]
                  const valCand = candProps[key]

                  const hasSrc = valSrc !== undefined && valSrc !== null && valSrc !== ''
                  const hasCand = valCand !== undefined && valCand !== null && valCand !== ''

                  const isMatch =
                    hasSrc && hasCand && String(valSrc).trim().toLowerCase() === String(valCand).trim().toLowerCase()
                  const isDiff = hasSrc && hasCand && !isMatch

                  return (
                    <tr
                      key={key}
                      className={
                        isMatch
                          ? 'bg-emerald-950/20'
                          : isDiff
                          ? 'bg-amber-950/20'
                          : ''
                      }
                    >
                      <td className="p-1.5 text-slate-400 font-semibold truncate max-w-[100px]" title={key}>
                        {key}
                      </td>
                      <td
                        className={`p-1.5 truncate max-w-[120px] ${
                          hasSrc ? (isMatch ? 'text-emerald-300' : 'text-slate-200') : 'text-slate-600 italic'
                        }`}
                        title={hasSrc ? String(valSrc) : '—'}
                      >
                        {hasSrc ? String(valSrc) : '—'}
                      </td>
                      <td
                        className={`p-1.5 truncate max-w-[120px] ${
                          hasCand ? (isMatch ? 'text-emerald-300' : isDiff ? 'text-amber-300' : 'text-slate-200') : 'text-slate-600 italic'
                        }`}
                        title={hasCand ? String(valCand) : '—'}
                      >
                        {hasCand ? String(valCand) : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* REVIEW HISTORY AUDIT TRAIL (Requirement 13) */}
        {/* ========================================================================= */}
        <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <History className="w-3.5 h-3.5 text-cyan-400" />
              Review & Audit History
            </span>
            <span className="text-[10px] text-slate-500 font-mono">
              {reviews.length} Decision{reviews.length === 1 ? '' : 's'}
            </span>
          </div>

          <div className="space-y-2">
            {/* Step 1: Initial Machine Generation */}
            <div className="p-2 rounded bg-surface-900 border border-border/80 flex items-start gap-2">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-200 text-[10px]">
                    MACHINE MATCH SUGGESTION
                  </span>
                  <span className="text-[9px] text-slate-500">
                    {new Date(created_at).toLocaleString()}
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  Machine Score: <strong className="text-cyan-300">{scorePct}%</strong> ({status.toUpperCase()})
                </div>
              </div>
            </div>

            {/* Historical Human Reviews */}
            {reviews && reviews.length > 0 ? (
              reviews.map((rev, idx) => (
                <div key={rev.id || idx} className="pl-4 border-l-2 border-cyan-800/60 ml-2 space-y-1">
                  <div className="p-2 rounded bg-surface-900 border border-border flex items-start gap-2">
                    {rev.decision === 'ACCEPTED' ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" />
                    ) : rev.decision === 'REJECTED' ? (
                      <XCircle className="w-3.5 h-3.5 text-rose-400 flex-shrink-0 mt-0.5" />
                    ) : (
                      <Flag className="w-3.5 h-3.5 text-orange-400 flex-shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span
                          className={`font-bold text-[10px] uppercase ${
                            rev.decision === 'ACCEPTED'
                              ? 'text-emerald-400'
                              : rev.decision === 'REJECTED'
                              ? 'text-rose-400'
                              : 'text-orange-400'
                          }`}
                        >
                          HUMAN {rev.decision}
                        </span>
                        <span className="text-[9px] text-slate-500">
                          {new Date(rev.created_at).toLocaleString()}
                        </span>
                      </div>
                      {rev.comment && (
                        <div className="text-[10px] text-slate-300 mt-1 italic bg-surface-950 p-1.5 rounded border border-border/50">
                          "{rev.comment}"
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-[10px] text-slate-500 italic p-2 bg-surface-900/50 rounded border border-border/40 text-center">
                No human decisions recorded yet. Relationship is currently PENDING.
              </div>
            )}
          </div>
        </div>

        {/* ========================================================================= */}
        {/* SIBLING CANDIDATES (if multiple candidates exist) */}
        {/* ========================================================================= */}
        {siblingCandidates && siblingCandidates.length > 1 && (
          <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                All Candidates for this Source
              </span>
              <span className="text-[10px] text-cyan-300 font-mono">
                {siblingCandidates.length} Total
              </span>
            </div>

            <div className="space-y-1.5">
              {siblingCandidates.map((cand) => {
                const isCurrent = cand.id === currentMatchId
                const candPct = Math.round(cand.overall_score * 100)

                return (
                  <button
                    key={cand.id}
                    onClick={() => onSelectMatch && onSelectMatch(cand.id)}
                    className={`w-full text-left p-2 rounded border transition-all flex items-center justify-between ${
                      isCurrent
                        ? 'bg-cyan-950/70 border-cyan-600 text-cyan-200'
                        : 'bg-surface-900 border-border/80 hover:bg-surface-850 text-slate-300'
                    }`}
                  >
                    <div className="min-w-0 pr-2">
                      <div className="flex items-center gap-1.5 text-[11px] font-bold truncate">
                        <span>{cand.candidate_identifier || 'Unknown'}</span>
                        <span className="text-[9px] text-slate-500">#{cand.rank}</span>
                      </div>
                      <div className="text-[9px] text-slate-400">
                        {cand.candidate_role} • {cand.review_status}
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <span className="font-mono font-bold text-xs">{candPct}%</span>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* MACHINE MULTI-SIGNAL SCORE BREAKDOWN */}
        {/* ========================================================================= */}
        <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
              Component Signal Scores
            </span>
            <span className="text-[10px] text-slate-500 font-mono">Normalized (0.0 - 1.0)</span>
          </div>

          <div className="space-y-2.5">
            {signals.map((sig) => {
              const isApplicable = sig.score !== null && sig.score !== undefined
              const pct = isApplicable ? Math.round((sig.score as number) * 100) : null

              return (
                <div key={sig.key} className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-300 font-medium">{sig.name}</span>
                    {isApplicable ? (
                      <span className="font-bold text-slate-200 font-mono">{pct}%</span>
                    ) : (
                      <span className="px-1.5 py-0.2 rounded bg-surface-850 text-slate-500 text-[10px]">
                        N/A (Renormalized)
                      </span>
                    )}
                  </div>

                  {/* Progress bar */}
                  <div className="w-full h-1.5 bg-surface-850 rounded-full overflow-hidden">
                    {isApplicable ? (
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          (pct ?? 0) >= 80
                            ? 'bg-emerald-400'
                            : (pct ?? 0) >= 60
                            ? 'bg-amber-400'
                            : (pct ?? 0) >= 40
                            ? 'bg-orange-500'
                            : 'bg-red-500'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    ) : (
                      <div className="h-full bg-slate-700/50 w-full" />
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Scoring Explanations / Reasons */}
        <div className="rounded-lg bg-surface-950 border border-border p-3 space-y-2">
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <span>Deterministic Explanation</span>
          </div>
          <ul className="space-y-1.5 text-[11px] text-slate-300">
            {explanation.reasons && explanation.reasons.length > 0 ? (
              explanation.reasons.map((r, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-cyan-400 font-bold">•</span>
                  <span className="leading-tight">{r}</span>
                </li>
              ))
            ) : (
              <li className="text-slate-500 italic">No specific explanations generated.</li>
            )}
          </ul>
        </div>
      </div>
    </div>
  )
}
