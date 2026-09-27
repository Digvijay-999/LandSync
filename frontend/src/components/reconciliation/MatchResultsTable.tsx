import React, { useState, useMemo } from 'react'
import {
  Filter,
  ArrowUpDown,
  Search,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  HelpCircle,
  Layers,
  ChevronLeft,
  ChevronRight,
  Star,
  Scale,
  Award,
} from 'lucide-react'
import type { FeatureMatchListItem, MatchStatus, CandidateRole } from '../../types'

interface MatchResultsTableProps {
  matches: FeatureMatchListItem[]
  selectedMatchId: string | null
  onSelectMatch: (matchId: string) => void
  isLoading: boolean
}

type SortField =
  | 'overall_score'
  | 'status'
  | 'rank'
  | 'candidate_role'
  | 'score_gap'
  | 'source_identifier'
  | 'candidate_identifier'
type SortOrder = 'asc' | 'desc'

export const MatchResultsTable: React.FC<MatchResultsTableProps> = ({
  matches,
  selectedMatchId,
  onSelectMatch,
  isLoading,
}) => {
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [roleFilter, setRoleFilter] = useState<string>('all')
  const [bestOnly, setBestOnly] = useState<boolean>(false)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [candidateDatasetFilter, setCandidateDatasetFilter] = useState<string>('all')
  const [minConfidence, setMinConfidence] = useState<number>(0)
  const [sortField, setSortField] = useState<SortField>('overall_score')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [page, setPage] = useState<number>(1)
  const pageSize = 15

  // Extract distinct candidate datasets for filter dropdown
  const candidateDatasets = useMemo(() => {
    const set = new Set<string>()
    matches.forEach((m) => {
      if (m.candidate_dataset_name) {
        set.add(m.candidate_dataset_name)
      }
    })
    return Array.from(set)
  }, [matches])

  // Filter and sort matches
  const filteredMatches = useMemo(() => {
    return matches
      .filter((m) => {
        if (statusFilter !== 'all' && m.status !== statusFilter) return false
        if (roleFilter !== 'all' && m.candidate_role !== roleFilter) return false
        if (bestOnly && !m.is_best_candidate) return false
        if (candidateDatasetFilter !== 'all' && m.candidate_dataset_name !== candidateDatasetFilter) {
          return false
        }
        if (m.overall_score < minConfidence / 100) return false

        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase()
          const sId = (m.source_identifier || '').toLowerCase()
          const cId = (m.candidate_identifier || '').toLowerCase()
          const sName = (m.source_dataset_name || '').toLowerCase()
          const cName = (m.candidate_dataset_name || '').toLowerCase()
          if (!sId.includes(q) && !cId.includes(q) && !sName.includes(q) && !cName.includes(q)) {
            return false
          }
        }

        return true
      })
      .sort((a, b) => {
        let comparison = 0
        if (sortField === 'overall_score') {
          comparison = a.overall_score - b.overall_score
        } else if (sortField === 'status') {
          comparison = a.status.localeCompare(b.status)
        } else if (sortField === 'rank') {
          comparison = (a.rank ?? 999) - (b.rank ?? 999)
        } else if (sortField === 'candidate_role') {
          comparison = (a.candidate_role || '').localeCompare(b.candidate_role || '')
        } else if (sortField === 'score_gap') {
          comparison = (a.score_gap ?? 0) - (b.score_gap ?? 0)
        } else if (sortField === 'source_identifier') {
          comparison = (a.source_identifier || '').localeCompare(b.source_identifier || '')
        } else if (sortField === 'candidate_identifier') {
          comparison = (a.candidate_identifier || '').localeCompare(b.candidate_identifier || '')
        }
        return sortOrder === 'asc' ? comparison : -comparison
      })
  }, [
    matches,
    statusFilter,
    roleFilter,
    bestOnly,
    candidateDatasetFilter,
    minConfidence,
    searchQuery,
    sortField,
    sortOrder,
  ])

  const totalPages = Math.ceil(filteredMatches.length / pageSize) || 1
  const paginatedMatches = useMemo(() => {
    const start = (page - 1) * pageSize
    return filteredMatches.slice(start, start + pageSize)
  }, [filteredMatches, page, pageSize])

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
  }

  const getStatusBadge = (st: MatchStatus) => {
    switch (st) {
      case 'matched':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-950/80 text-emerald-300 border border-emerald-800">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            Matched
          </span>
        )
      case 'possible_match':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-950/80 text-amber-300 border border-amber-800">
            <HelpCircle className="w-3 h-3 text-amber-400" />
            Possible
          </span>
        )
      case 'conflict':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-red-950/80 text-red-300 border border-red-800">
            <AlertTriangle className="w-3 h-3 text-red-400" />
            Conflict
          </span>
        )
      case 'unmatched':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
            <AlertCircle className="w-3 h-3 text-slate-400" />
            Unmatched
          </span>
        )
    }
  }

  const getRoleBadge = (role?: CandidateRole | null, rank?: number | null) => {
    switch (role) {
      case 'BEST':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-950/90 text-emerald-300 border border-emerald-700 shadow-sm">
            <Star className="w-3 h-3 text-emerald-400 fill-emerald-400" />
            BEST #{rank || 1}
          </span>
        )
      case 'AMBIGUOUS':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-950/90 text-amber-300 border border-amber-700 shadow-sm" title="Multiple candidates scored within tie tolerance (0.015)">
            <Scale className="w-3 h-3 text-amber-400" />
            AMBIGUOUS #{rank || 1}
          </span>
        )
      case 'SECONDARY':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
            SECONDARY #{rank || 2}
          </span>
        )
      case 'CONFLICT':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-red-950/90 text-red-300 border border-red-700">
            <AlertTriangle className="w-3 h-3 text-red-400" />
            CONFLICT
          </span>
        )
      case 'UNMATCHED':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider bg-surface-800 text-slate-400 border border-border">
            UNMATCHED
          </span>
        )
    }
  }

  const renderScoreGap = (m: FeatureMatchListItem) => {
    if (m.score_gap === null || m.score_gap === undefined) {
      return <span className="text-slate-500">-</span>
    }
    const gapPct = (m.score_gap * 100).toFixed(1)
    if (m.candidate_role === 'AMBIGUOUS') {
      return (
        <span className="text-amber-400 font-mono text-[10px]" title="Tied within tie tolerance">
          Δ {gapPct}% (Tie)
        </span>
      )
    }
    if (m.rank === 1) {
      return (
        <span className="text-emerald-400 font-mono text-[10px]" title="Lead margin over rank #2">
          +{gapPct}% gap
        </span>
      )
    }
    return (
      <span className="text-slate-400 font-mono text-[10px]" title="Behind top candidate">
        -{gapPct}%
      </span>
    )
  }

  return (
    <div className="flex flex-col bg-surface-900 border-t border-border font-mono text-xs select-none">
      {/* Table Filter & Search Controls */}
      <div className="p-2.5 bg-surface-950/90 border-b border-border flex flex-wrap items-center justify-between gap-2.5 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Filter */}
          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setPage(1)
              }}
              className="bg-surface-850 border border-border rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-cyan-500 text-[11px]"
            >
              <option value="all">All Classifications</option>
              <option value="matched">Matched (≥80%)</option>
              <option value="possible_match">Possible (60–79%)</option>
              <option value="conflict">Conflict (Discrepancy)</option>
              <option value="unmatched">Unmatched (No Cand.)</option>
            </select>
          </div>

          {/* Candidate Role Filter */}
          <div className="flex items-center gap-1.5">
            <Award className="w-3.5 h-3.5 text-cyan-400" />
            <select
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value)
                setPage(1)
              }}
              className="bg-surface-850 border border-border rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-cyan-500 text-[11px]"
            >
              <option value="all">All Roles</option>
              <option value="BEST">★ Best Candidate</option>
              <option value="AMBIGUOUS">Ambiguous (Tied)</option>
              <option value="SECONDARY">Secondary Candidates</option>
              <option value="CONFLICT">Conflict Candidates</option>
              <option value="UNMATCHED">Unmatched</option>
            </select>
          </div>

          {/* Best Only Quick Toggle */}
          <button
            type="button"
            onClick={() => {
              setBestOnly(!bestOnly)
              setPage(1)
            }}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-semibold border transition-all ${
              bestOnly
                ? 'bg-emerald-950/80 text-emerald-300 border-emerald-600'
                : 'bg-surface-850 text-slate-400 border-border hover:text-slate-200'
            }`}
          >
            <Star className={`w-3 h-3 ${bestOnly ? 'fill-emerald-400 text-emerald-400' : ''}`} />
            <span>Best Only</span>
          </button>

          {/* Candidate Dataset Filter */}
          {candidateDatasets.length > 1 && (
            <div className="flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={candidateDatasetFilter}
                onChange={(e) => {
                  setCandidateDatasetFilter(e.target.value)
                  setPage(1)
                }}
                className="bg-surface-850 border border-border rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-cyan-500 text-[11px]"
              >
                <option value="all">All Candidate Datasets</option>
                {candidateDatasets.map((ds) => (
                  <option key={ds} value={ds}>
                    {ds}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Min Confidence Slider */}
          <div className="flex items-center gap-1.5 pl-1">
            <span className="text-slate-400 text-[11px]">Min Conf:</span>
            <input
              type="range"
              min="0"
              max="90"
              step="10"
              value={minConfidence}
              onChange={(e) => {
                setMinConfidence(Number(e.target.value))
                setPage(1)
              }}
              className="w-16 accent-cyan-400 h-1 bg-surface-800 rounded"
            />
            <span className="text-cyan-300 font-bold w-6 text-[11px]">{minConfidence}%</span>
          </div>

          {/* Quick Search */}
          <div className="relative">
            <Search className="w-3 h-3 text-slate-500 absolute left-2 top-2" />
            <input
              type="text"
              placeholder="Search ID / name..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value)
                setPage(1)
              }}
              className="bg-surface-850 border border-border rounded pl-6 pr-2 py-1 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 text-[11px] w-40"
            />
          </div>
        </div>

        {/* Counter Info */}
        <div className="flex items-center gap-3 text-slate-400 text-[11px]">
          <span>
            Showing <strong className="text-cyan-300">{filteredMatches.length}</strong> of{' '}
            {matches.length} matches
          </span>
        </div>
      </div>

      {/* Main Table */}
      <div className="overflow-x-auto max-h-[260px] overflow-y-auto">
        <table className="w-full text-left border-collapse">
          <thead className="bg-surface-950 sticky top-0 border-b border-border text-slate-400 text-[10px] uppercase font-bold tracking-wider z-10">
            <tr>
              <th
                onClick={() => toggleSort('source_identifier')}
                className="py-2 px-3 cursor-pointer hover:text-slate-200 transition-colors"
              >
                <div className="flex items-center gap-1">
                  <span>Source Feature</span>
                  <ArrowUpDown className="w-3 h-3 text-slate-500" />
                </div>
              </th>
              <th
                onClick={() => toggleSort('candidate_identifier')}
                className="py-2 px-3 cursor-pointer hover:text-slate-200 transition-colors"
              >
                <div className="flex items-center gap-1">
                  <span>Candidate Feature</span>
                  <ArrowUpDown className="w-3 h-3 text-slate-500" />
                </div>
              </th>
              <th
                onClick={() => toggleSort('candidate_role')}
                className="py-2 px-3 cursor-pointer hover:text-slate-200 transition-colors"
              >
                <div className="flex items-center gap-1">
                  <span>Role & Rank</span>
                  <ArrowUpDown className="w-3 h-3 text-slate-500" />
                </div>
              </th>
              <th
                onClick={() => toggleSort('score_gap')}
                className="py-2 px-3 cursor-pointer hover:text-slate-200 transition-colors"
              >
                <div className="flex items-center gap-1">
                  <span>Score Gap</span>
                  <ArrowUpDown className="w-3 h-3 text-slate-500" />
                </div>
              </th>
              <th
                onClick={() => toggleSort('overall_score')}
                className="py-2 px-3 cursor-pointer hover:text-slate-200 transition-colors text-right"
              >
                <div className="flex items-center justify-end gap-1">
                  <span>Score</span>
                  <ArrowUpDown className="w-3 h-3 text-slate-500" />
                </div>
              </th>
              <th
                onClick={() => toggleSort('status')}
                className="py-2 px-3 cursor-pointer hover:text-slate-200 transition-colors"
              >
                <div className="flex items-center gap-1">
                  <span>Status</span>
                  <ArrowUpDown className="w-3 h-3 text-slate-500" />
                </div>
              </th>
              <th className="py-2 px-3 text-center">Signals (S / C / A / G / Att)</th>
              <th className="py-2 px-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {isLoading ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-slate-400">
                  <div className="flex items-center justify-center gap-2">
                    <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                    <span>Loading matches...</span>
                  </div>
                </td>
              </tr>
            ) : paginatedMatches.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-slate-500">
                  No match results match the selected filters.
                </td>
              </tr>
            ) : (
              paginatedMatches.map((m) => {
                const isSelected = selectedMatchId === m.id
                const scorePct = Math.round(m.overall_score * 100)

                return (
                  <tr
                    key={m.id}
                    onClick={() => onSelectMatch(m.id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-cyan-950/40 border-l-2 border-l-cyan-400'
                        : 'hover:bg-surface-850/60'
                    }`}
                  >
                    {/* Source Feature */}
                    <td className="py-2 px-3">
                      <div className="font-semibold text-slate-200 truncate max-w-[170px]">
                        {m.source_identifier || 'Source Feature'}
                      </div>
                      <div className="text-[10px] text-cyan-400 truncate max-w-[170px]">
                        {m.source_dataset_name} ({m.source_geometry_type})
                      </div>
                    </td>

                    {/* Candidate Feature */}
                    <td className="py-2 px-3">
                      {m.candidate_identifier ? (
                        <>
                          <div className="font-semibold text-slate-200 truncate max-w-[170px] flex items-center gap-1.5">
                            <span className="truncate">{m.candidate_identifier}</span>
                            {m.candidate_count && m.candidate_count > 1 && (
                              <span className="px-1 py-0.2 rounded bg-surface-800 text-slate-400 text-[9px] border border-border">
                                {m.candidate_count} cands
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] text-amber-400 truncate max-w-[170px]">
                            {m.candidate_dataset_name} ({m.candidate_geometry_type})
                          </div>
                        </>
                      ) : (
                        <span className="text-slate-500 italic">No candidate in tolerance</span>
                      )}
                    </td>

                    {/* Role & Rank */}
                    <td className="py-2 px-3">{getRoleBadge(m.candidate_role, m.rank)}</td>

                    {/* Score Gap */}
                    <td className="py-2 px-3">{renderScoreGap(m)}</td>

                    {/* Overall Score */}
                    <td className="py-2 px-3 text-right">
                      <div
                        className={`font-black font-mono text-sm ${
                          scorePct >= 80
                            ? 'text-emerald-400'
                            : scorePct >= 60
                            ? 'text-amber-400'
                            : scorePct >= 40
                            ? 'text-orange-400'
                            : 'text-slate-400'
                        }`}
                      >
                        {scorePct}%
                      </div>
                    </td>

                    {/* Status */}
                    <td className="py-2 px-3">{getStatusBadge(m.status)}</td>

                    {/* Key Signals Mini-Bar */}
                    <td className="py-2 px-3 text-center">
                      <div className="inline-flex items-center gap-1.5 text-[10px] font-mono text-slate-400">
                        <span title="Spatial Overlap">
                          {m.spatial_score !== null && m.spatial_score !== undefined
                            ? `${Math.round(m.spatial_score * 100)}`
                            : '-'}
                        </span>
                        <span className="text-slate-600">/</span>
                        <span title="Centroid Distance">
                          {m.centroid_score !== null && m.centroid_score !== undefined
                            ? `${Math.round(m.centroid_score * 100)}`
                            : '-'}
                        </span>
                        <span className="text-slate-600">/</span>
                        <span title="Area Ratio">
                          {m.area_score !== null && m.area_score !== undefined
                            ? `${Math.round(m.area_score * 100)}`
                            : '-'}
                        </span>
                        <span className="text-slate-600">/</span>
                        <span title="Geometry Contours">
                          {m.geometry_score !== null && m.geometry_score !== undefined
                            ? `${Math.round(m.geometry_score * 100)}`
                            : '-'}
                        </span>
                        <span className="text-slate-600">/</span>
                        <span title="Attribute Alignment">
                          {m.attribute_score !== null && m.attribute_score !== undefined
                            ? `${Math.round(m.attribute_score * 100)}`
                            : '-'}
                        </span>
                      </div>
                    </td>

                    {/* Action Button */}
                    <td className="py-2 px-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onSelectMatch(m.id)
                        }}
                        className={`px-2 py-1 rounded text-[10px] font-semibold border transition-all ${
                          isSelected
                            ? 'bg-cyan-500 text-surface-950 border-cyan-400'
                            : 'bg-surface-850 text-slate-300 border-border hover:bg-surface-800 hover:text-cyan-300'
                        }`}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="p-2.5 bg-surface-950 border-t border-border flex items-center justify-between text-slate-400 text-[11px]">
        <div>
          Page <strong className="text-slate-200">{page}</strong> of{' '}
          <strong className="text-slate-200">{totalPages}</strong>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="p-1 rounded bg-surface-850 hover:bg-surface-800 disabled:opacity-40 disabled:cursor-not-allowed border border-border text-slate-300"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="p-1 rounded bg-surface-850 hover:bg-surface-800 disabled:opacity-40 disabled:cursor-not-allowed border border-border text-slate-300"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}
