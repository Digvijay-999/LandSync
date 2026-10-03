import React, { useState, useRef, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import {
  Sparkles,
  X,
  Send,
  Loader2,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  Clock,
  Layers,
  FileText,
  AlertTriangle,
  MapPin,
  Compass,
  ArrowRight,
  Database,
  History,
  Tag,
  Scale,
} from 'lucide-react'
import { useAppStore } from '../../stores/useAppStore'
import {
  useAssistantHealth,
  useSuggestedQuestions,
  useAssistantQuery,
  useReindexProject,
} from '../../hooks/useAssistant'
import type {
  AssistantEvidenceSource,
  AssistantQueryResponse,
} from '../../types'

interface ChatMessage {
  id: string
  sender: 'user' | 'assistant'
  text?: string
  response?: AssistantQueryResponse
  timestamp: string
}

interface DemoPrompt {
  id: string
  label: string
  query: string
  category: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  borderColor: string
  bgColor: string
}

const DEMO_PROMPTS: DemoPrompt[] = [
  {
    id: 'quarantine-104',
    label: 'Parcel #104 Quarantine',
    query: 'Explain why Parcel #104 was quarantined',
    category: 'Quarantine',
    icon: AlertTriangle,
    color: 'text-amber-400',
    borderColor: 'border-amber-500/30 hover:border-amber-400/60',
    bgColor: 'bg-amber-950/20 hover:bg-amber-950/40',
  },
  {
    id: 'highest-risk',
    label: 'Highest-Risk Parcels',
    query: 'Show me the highest-risk parcels',
    category: 'Risk',
    icon: Scale,
    color: 'text-rose-400',
    borderColor: 'border-rose-500/30 hover:border-rose-400/60',
    bgColor: 'bg-rose-950/20 hover:bg-rose-950/40',
  },
  {
    id: 'authoritative-records',
    label: 'Authoritative Records Created',
    query: 'How many authoritative unified records were created?',
    category: 'Authoritative',
    icon: ShieldCheck,
    color: 'text-emerald-400',
    borderColor: 'border-emerald-500/30 hover:border-emerald-400/60',
    bgColor: 'bg-emerald-950/20 hover:bg-emerald-950/40',
  },
  {
    id: 'provenance-ulr',
    label: 'Provenance for ULR-PUN-HAV-0012',
    query: 'Show the provenance chain for ULR-PUN-HAV-0012',
    category: 'Provenance',
    icon: History,
    color: 'text-cyan-400',
    borderColor: 'border-cyan-500/30 hover:border-cyan-400/60',
    bgColor: 'bg-cyan-950/20 hover:bg-cyan-950/40',
  },
  {
    id: 'geometry-conflicts',
    label: 'Geometry Conflicts List',
    query: 'Which parcels have geometry conflicts?',
    category: 'Conflicts',
    icon: Layers,
    color: 'text-orange-400',
    borderColor: 'border-orange-500/30 hover:border-orange-400/60',
    bgColor: 'bg-orange-950/20 hover:bg-orange-950/40',
  },
  {
    id: 'pune-reconciliation',
    label: 'Pune Haveli Reconciliation',
    query: 'Summarize the Pune Haveli reconciliation',
    category: 'Summary',
    icon: Compass,
    color: 'text-blue-400',
    borderColor: 'border-blue-500/30 hover:border-blue-400/60',
    bgColor: 'bg-blue-950/20 hover:bg-blue-950/40',
  },
]

export const AssistantDrawer: React.FC = () => {
  const { projectId: routeProjectId } = useParams<{ projectId?: string }>()
  const {
    assistantOpen,
    assistantContextRecordId,
    assistantContextConflictId,
    activeProjectId,
    closeAssistant,
    openAssistantWithRecord,
    setActiveSpatialAnalysis,
  } = useAppStore()

  const effectiveProjectId = activeProjectId || routeProjectId || null

  const [inputQuery, setInputQuery] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [expandedReasoning, setExpandedReasoning] = useState<Record<string, boolean>>({})
  const [expandedCitations, setExpandedCitations] = useState<Record<string, boolean>>({})

  const chatEndRef = useRef<HTMLDivElement>(null)

  const { data: health } = useAssistantHealth()
  const { data: suggestedData, isLoading: loadingSuggestions } = useSuggestedQuestions(
    effectiveProjectId || undefined,
    assistantContextRecordId || undefined
  )

  const queryMutation = useAssistantQuery()
  const reindexMutation = useReindexProject()

  // Auto-scroll to bottom of chat
  useEffect(() => {
    if (assistantOpen) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, assistantOpen, queryMutation.isPending])

  const handleSend = (queryToSend?: string) => {
    const q = (queryToSend || inputQuery).trim()
    if (!q || !effectiveProjectId || queryMutation.isPending) return

    const userMsgId = `user-${Date.now()}`
    const userMsg: ChatMessage = {
      id: userMsgId,
      sender: 'user',
      text: q,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMsg])
    setInputQuery('')

    queryMutation.mutate(
      {
        query: q,
        project_id: effectiveProjectId,
        context_record_id: assistantContextRecordId,
        context_conflict_id: assistantContextConflictId,
      },
      {
        onSuccess: (data) => {
          const assistantMsg: ChatMessage = {
            id: `assistant-${Date.now()}`,
            sender: 'assistant',
            response: data,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          }
          setMessages((prev) => [...prev, assistantMsg])
        },
      }
    )
  }

  const toggleReasoning = (msgId: string) => {
    setExpandedReasoning((prev) => ({ ...prev, [msgId]: !prev[msgId] }))
  }

  const toggleCitations = (msgId: string) => {
    setExpandedCitations((prev) => ({ ...prev, [msgId]: !prev[msgId] }))
  }

  if (!assistantOpen) return null

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[500px] md:w-[560px] bg-surface-900/98 backdrop-blur-md border-l border-border shadow-2xl flex flex-col transition-all duration-300 ease-in-out">
      {/* Top Header */}
      <div className="p-4 border-b border-border flex items-center justify-between bg-surface-950/70">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500/20 to-blue-600/30 border border-cyan-500/40 flex items-center justify-center text-cyan-400 shadow-sm">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-100 tracking-wide font-mono">
                LANDSYNC EVIDENCE ASSISTANT
              </h2>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/80">
                M8 AI
              </span>
            </div>
            <p className="text-[11px] text-slate-400 flex items-center gap-1.5 mt-0.5">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>{health?.configured_provider || 'Deterministic Grounded'}</span>
              <span className="text-slate-600">•</span>
              <span>100% Read-Only Evidence Guard</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {effectiveProjectId && (
            <button
              onClick={() => reindexMutation.mutate(effectiveProjectId)}
              disabled={reindexMutation.isPending}
              className="p-1.5 rounded-md text-xs font-mono text-slate-400 hover:text-cyan-300 hover:bg-surface-800 transition-colors flex items-center gap-1 disabled:opacity-50"
              title="Re-index project evidence vectors in PostgreSQL"
            >
              <Database className={`w-3.5 h-3.5 ${reindexMutation.isPending ? 'animate-spin text-cyan-400' : ''}`} />
              <span className="hidden sm:inline text-[11px]">Re-index</span>
            </button>
          )}

          <button
            onClick={closeAssistant}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-200 hover:bg-surface-800 transition-colors"
            title="Close Assistant"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Context Banner */}
      {(assistantContextRecordId || assistantContextConflictId) && (
        <div className="px-4 py-2 bg-cyan-950/40 border-b border-cyan-900/40 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-cyan-300">
            <Tag className="w-3.5 h-3.5" />
            <span className="font-mono">
              Focus: {assistantContextRecordId ? `Unified Record (${assistantContextRecordId.slice(0, 8)}...)` : `Conflict (${assistantContextConflictId?.slice(0, 8)}...)`}
            </span>
          </div>
          <button
            onClick={() => {
              useAppStore.setState({
                assistantContextRecordId: null,
                assistantContextConflictId: null,
              })
            }}
            className="text-[11px] text-cyan-400 hover:text-cyan-200 underline"
          >
            Clear Focus
          </button>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="py-6 px-2 space-y-5">
            <div className="p-4 rounded-xl bg-surface-950/80 border border-border space-y-2.5">
              <div className="flex items-center gap-2 text-cyan-400 font-medium text-xs font-mono">
                <ShieldCheck className="w-4 h-4" />
                <span>EVIDENCE-FIRST GEOSPATIAL INTELLIGENCE</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Ask questions about parcel boundaries, attribute discrepancies, spatial IoU overlaps,
                or complete provenance lineages. Every claim is strictly grounded in database evidence
                and PostGIS metrics with zero autonomous data alterations.
              </p>
            </div>

            {/* Demo Prompt Scenarios */}
            <div className="space-y-2.5">
              <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-cyan-400 font-semibold">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>DEMO PROMPT SCENARIOS</span>
                </span>
                <span className="text-[10px] text-slate-400 font-mono">1-Click Live Reasoning</span>
              </div>

              <div className="grid grid-cols-1 gap-2">
                {DEMO_PROMPTS.map((prompt) => {
                  const Icon = prompt.icon
                  return (
                    <button
                      key={prompt.id}
                      onClick={() => handleSend(prompt.query)}
                      disabled={queryMutation.isPending || !effectiveProjectId}
                      className={`w-full text-left p-2.5 rounded-lg ${prompt.bgColor} border ${prompt.borderColor} text-slate-300 hover:text-white transition-all flex items-start justify-between gap-2.5 group disabled:opacity-50 disabled:pointer-events-none shadow-sm`}
                    >
                      <div className="flex items-start gap-2.5 min-w-0">
                        <div className={`p-1.5 rounded-md bg-surface-950/90 border border-border/80 ${prompt.color} shrink-0 mt-0.5 shadow-xs`}>
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-medium text-slate-200 group-hover:text-cyan-200 transition-colors">
                              {prompt.label}
                            </span>
                            <span className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded border border-border/80 bg-surface-950/80 ${prompt.color}`}>
                              {prompt.category}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-400 truncate mt-0.5 group-hover:text-slate-200">
                            "{prompt.query}"
                          </p>
                        </div>
                      </div>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 shrink-0 mt-2 transition-transform group-hover:translate-x-0.5" />
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Dynamic Context Inquiries */}
            <div className="space-y-2 pt-2 border-t border-border/60">
              <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Compass className="w-3.5 h-3.5 text-cyan-400" />
                <span>Contextual Investigations</span>
              </div>

              {loadingSuggestions ? (
                <div className="text-xs text-slate-500 flex items-center gap-2 py-2 font-mono">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                  Generating tailored questions...
                </div>
              ) : (
                <div className="space-y-1.5">
                  {(suggestedData?.suggested_questions || [
                    'Provide an executive overview of this LandSync project and harmonization status.',
                    'Why are attribute conflicts flagged and which records are affected?',
                    'Compare parcel boundaries and geometry deltas between cadastral and drone datasets.',
                  ]).map((question, i) => (
                    <button
                      key={i}
                      onClick={() => handleSend(question)}
                      disabled={queryMutation.isPending || !effectiveProjectId}
                      className="w-full text-left p-2.5 rounded-lg bg-surface-950/60 hover:bg-surface-800/80 border border-border hover:border-cyan-800/60 text-xs text-slate-300 hover:text-cyan-200 transition-all flex items-start justify-between gap-2 group disabled:opacity-50 disabled:pointer-events-none"
                    >
                      <span className="leading-snug">{question}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 shrink-0 mt-0.5 transition-colors" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
            >
              {msg.sender === 'user' ? (
                <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-gradient-to-r from-cyan-600 to-blue-600 text-white p-3 text-xs shadow-md">
                  <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                  <span className="text-[10px] text-cyan-200/70 block text-right mt-1 font-mono">
                    {msg.timestamp}
                  </span>
                </div>
              ) : (
                <div className="max-w-[95%] w-full rounded-2xl rounded-tl-sm bg-surface-950 border border-border p-3.5 text-xs text-slate-200 shadow-lg space-y-3">
                  {/* Assistant Message Header Meta */}
                  {msg.response && (
                    <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-border/60 text-[11px] font-mono">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/80 font-semibold">
                          {msg.response.intent}
                        </span>
                        <span className="flex items-center gap-1 text-slate-400">
                          <Clock className="w-3 h-3" />
                          <span>{msg.response.execution_time_ms}ms</span>
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <ShieldCheck
                          className={`w-3.5 h-3.5 ${
                            msg.response.grounded_score >= 0.8
                              ? 'text-emerald-400'
                              : 'text-amber-400'
                          }`}
                        />
                        <span
                          className={`font-semibold ${
                            msg.response.grounded_score >= 0.8
                              ? 'text-emerald-400'
                              : 'text-amber-400'
                          }`}
                        >
                          {Math.round(msg.response.grounded_score * 100)}% Grounded
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Formatted Answer Body */}
                  <div className="prose prose-invert prose-xs max-w-none text-slate-200 leading-relaxed font-sans space-y-2 whitespace-pre-wrap">
                    {msg.response?.answer}
                  </div>

                  {/* Spatial Plan Badge */}
                  {msg.response?.spatial_plan && (
                    <div className="flex flex-wrap items-center gap-1.5 p-2 rounded bg-surface-900 border border-border text-[10px] text-slate-300">
                      <span className="font-semibold text-cyan-400">Spatial Plan:</span>
                      {msg.response.spatial_plan.target_dataset_name && (
                        <span className="px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                          Target: {msg.response.spatial_plan.target_dataset_name}
                        </span>
                      )}
                      {msg.response.spatial_plan.reference_dataset_name && (
                        <span className="px-1.5 py-0.5 rounded bg-surface-800 text-slate-300 border border-border">
                          Ref: {msg.response.spatial_plan.reference_dataset_name}
                        </span>
                      )}
                      <span className="text-slate-400 font-mono">
                        {msg.response.spatial_plan.distance}m
                      </span>
                    </div>
                  )}

                  {/* Advisory Conflict Resolution Proposal Card */}
                  {msg.response?.conflict_proposal && (
                    <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-800/70 space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-amber-300 font-bold text-xs">
                          <Scale className="w-3.5 h-3.5 text-amber-400" />
                          <span>Advisory Resolution Proposal</span>
                        </div>
                        <span className="px-1.5 py-0.5 rounded bg-amber-950 border border-amber-800 text-[10px] text-amber-400 font-mono">
                          {Math.round(msg.response.conflict_proposal.confidence * 100)}% Confidence
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-200 space-y-1">
                        <div>
                          <span className="text-slate-400">Target Field: </span>
                          <strong className="text-amber-300">{msg.response.conflict_proposal.attribute_name}</strong> on record <strong className="text-slate-100">{msg.response.conflict_proposal.record_identifier}</strong>
                        </div>
                        <div>
                          <span className="text-slate-400">Proposed Value: </span>
                          <span className="font-mono px-1.5 py-0.5 rounded bg-surface-900 text-emerald-400 font-bold border border-border">
                            {String(msg.response.conflict_proposal.recommended_value)}
                          </span>
                          <span className="text-slate-400 ml-1.5">via authority '{msg.response.conflict_proposal.recommended_source}'</span>
                        </div>
                      </div>

                      <div className="text-[10px] text-slate-300 p-2 rounded bg-surface-950/80 border border-amber-900/40 space-y-1">
                        <p><strong className="text-slate-400">Fact:</strong> {msg.response.conflict_proposal.fact_statement}</p>
                        <p><strong className="text-slate-400">Inference:</strong> {msg.response.conflict_proposal.inference_statement}</p>
                        <p><strong className="text-slate-400">Recommendation:</strong> {msg.response.conflict_proposal.recommendation_statement}</p>
                      </div>

                      <p className="text-[9px] text-amber-400/80 italic">
                        {msg.response.conflict_proposal.disclaimer}
                      </p>
                    </div>
                  )}

                  {/* Interactive Spatial Analysis Map Result Card */}
                  {msg.response?.spatial_result && (
                    <div className="p-2.5 rounded-lg bg-cyan-950/40 border border-cyan-800/80 space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-cyan-300 font-semibold text-xs">
                          <Compass className="w-3.5 h-3.5 text-cyan-400" />
                          <span>{msg.response.spatial_result.title}</span>
                        </div>
                        <span className="px-1.5 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-[10px] text-cyan-400 font-bold">
                          {msg.response.spatial_result.result_count} items
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-300">
                        {msg.response.spatial_result.description}
                      </p>
                      <button
                        onClick={() => {
                          if (msg.response?.spatial_result) {
                            setActiveSpatialAnalysis(msg.response.spatial_result)
                          }
                        }}
                        className="w-full py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 transition-colors shadow-sm"
                      >
                        <MapPin className="w-3 h-3" />
                        <span>Visualize Spatial Result on Map</span>
                      </button>
                    </div>
                  )}

                  {/* Expandable Reasoning Trace */}
                  {msg.response && msg.response.reasoning_steps.length > 0 && (
                    <div className="pt-2 border-t border-border/40">
                      <button
                        onClick={() => toggleReasoning(msg.id)}
                        className="flex items-center justify-between w-full text-[11px] font-mono text-slate-400 hover:text-slate-200 py-1"
                      >
                        <span className="flex items-center gap-1.5">
                          <Compass className="w-3 h-3 text-cyan-400" />
                          <span>Reasoning Steps ({msg.response.reasoning_steps.length})</span>
                        </span>
                        {expandedReasoning[msg.id] ? (
                          <ChevronUp className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5" />
                        )}
                      </button>

                      {expandedReasoning[msg.id] && (
                        <div className="mt-2 p-2.5 rounded-lg bg-surface-900 border border-border/80 space-y-1.5 font-mono text-[11px] text-slate-300">
                          {msg.response.reasoning_steps.map((step, idx) => (
                            <div key={idx} className="flex items-start gap-2">
                              <span className="text-cyan-500 font-bold shrink-0">{idx + 1}.</span>
                              <span className="leading-snug">{step}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Evidence Sources Citations */}
                  {msg.response && msg.response.evidence_sources.length > 0 && (
                    <div className="pt-2 border-t border-border/40">
                      <button
                        onClick={() => toggleCitations(msg.id)}
                        className="flex items-center justify-between w-full text-[11px] font-mono text-slate-400 hover:text-slate-200 py-1"
                      >
                        <span className="flex items-center gap-1.5">
                          <Database className="w-3 h-3 text-cyan-400" />
                          <span>Grounded Evidence Citations ({msg.response.evidence_sources.length})</span>
                        </span>
                        {expandedCitations[msg.id] ? (
                          <ChevronUp className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5" />
                        )}
                      </button>

                      {expandedCitations[msg.id] && (
                        <div className="mt-2 space-y-2">
                          {msg.response.evidence_sources.map((ev, idx) => (
                            <div
                              key={idx}
                              className="p-2 rounded-lg bg-surface-900 border border-border/70 hover:border-cyan-800/70 transition-colors text-[11px] space-y-1"
                            >
                              <div className="flex items-center justify-between gap-1">
                                <span className="font-mono font-semibold text-cyan-300">
                                  {ev.title}
                                </span>
                                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-surface-950 text-slate-400 border border-border">
                                  {ev.source_type}
                                </span>
                              </div>
                              <p className="text-slate-400 text-[11px] leading-relaxed">
                                {ev.relevance_note}
                              </p>
                              {ev.properties && Object.keys(ev.properties).length > 0 && (
                                <div className="text-[10px] text-slate-500 font-mono truncate pt-0.5">
                                  ID: {ev.identifier}
                                  {ev.role && ` • Role: ${ev.role}`}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Followup Question Pills */}
                  {msg.response && msg.response.suggested_followups.length > 0 && (
                    <div className="pt-2 border-t border-border/40 space-y-1.5">
                      <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider block">
                        Suggested Follow-ups
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {msg.response.suggested_followups.map((fQ, fIdx) => (
                          <button
                            key={fIdx}
                            onClick={() => handleSend(fQ)}
                            className="px-2.5 py-1 rounded-full bg-surface-900 hover:bg-cyan-950 border border-border hover:border-cyan-800 text-[11px] text-slate-300 hover:text-cyan-300 transition-colors text-left"
                          >
                            {fQ}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <span className="text-[10px] text-slate-500 block text-right mt-1 font-mono">
                    {msg.timestamp}
                  </span>
                </div>
              )}
            </div>
          ))
        )}

        {/* Loading Indicator */}
        {queryMutation.isPending && (
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 p-3 rounded-xl bg-surface-950 border border-border w-fit animate-pulse">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Analyzing PostGIS evidence and orchestrating GIS tools...</span>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Quick Demo Chips Bar */}
      <div className="px-3 pt-2.5 pb-2 border-t border-border/70 bg-surface-950/95">
        <div className="flex items-center justify-between mb-1.5 text-[10px] font-mono text-slate-400">
          <span className="flex items-center gap-1.5 text-cyan-400 font-semibold">
            <Sparkles className="w-3 h-3" />
            <span>DEMO CHIPS</span>
          </span>
          <span className="text-[10px] text-slate-400">Quick-inject queries</span>
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar scroll-smooth">
          {DEMO_PROMPTS.map((p) => {
            const Icon = p.icon
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => handleSend(p.query)}
                disabled={queryMutation.isPending || !effectiveProjectId}
                title={p.query}
                className={`shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${p.borderColor} ${p.bgColor} text-slate-300 hover:text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-xs`}
              >
                <Icon className={`w-3 h-3 ${p.color}`} />
                <span>{p.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Bottom Query Input */}
      <div className="p-3 pt-2 border-t border-border/40 bg-surface-950/80">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSend()
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            placeholder={
              assistantContextRecordId
                ? 'Ask about this record or its conflicts...'
                : 'Ask about parcels, conflicts, proximity, or provenance...'
            }
            disabled={queryMutation.isPending || !effectiveProjectId}
            className="flex-1 bg-surface-900 border border-border focus:border-cyan-500 focus:outline-none rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!inputQuery.trim() || queryMutation.isPending || !effectiveProjectId}
            className="p-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:bg-surface-800 text-white disabled:text-slate-500 transition-colors shadow-sm"
          >
            {queryMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </form>

        {!effectiveProjectId && (
          <p className="text-[11px] text-amber-400 mt-1 font-mono">
            * Select an active project from the sidebar to query the assistant.
          </p>
        )}
      </div>
    </div>
  )
}
