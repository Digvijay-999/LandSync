import React from 'react'
import { CheckCircle2, Clock, RotateCw, Lock, Sparkles, AlertCircle } from 'lucide-react'
import type { PipelineStageItem } from '../../types'

export interface PipelineIndicatorProps {
  stages?: PipelineStageItem[]
  selectedStageNumber?: number
  onSelectStage?: (stageNumber: number) => void
  runningStageNumber?: number | null
}

const DEFAULT_STAGES: Array<{ stage_number: number; stage_id: string; name: string }> = [
  { stage_number: 1, stage_id: 'ingestion', name: 'Data Ingestion' },
  { stage_number: 2, stage_id: 'profiling', name: 'Data Profiling' },
  { stage_number: 3, stage_id: 'crs', name: 'CRS Normalization' },
  { stage_number: 4, stage_id: 'schema', name: 'Schema Normalization' },
  { stage_number: 5, stage_id: 'candidate', name: 'Spatial Candidate Gen' },
  { stage_number: 6, stage_id: 'matching', name: 'Feature Matching' },
  { stage_number: 7, stage_id: 'harmonization', name: 'Attribute/Geometry Harmonization' },
  { stage_number: 8, stage_id: 'conflict', name: 'Conflict Detection' },
  { stage_number: 9, stage_id: 'validation', name: 'Validation' },
  { stage_number: 10, stage_id: 'scoring', name: 'Confidence Scoring' },
  { stage_number: 11, stage_id: 'review', name: 'Human Review' },
  { stage_number: 12, stage_id: 'record', name: 'Unified Record' },
  { stage_number: 13, stage_id: 'provenance', name: 'Provenance' },
  { stage_number: 14, stage_id: 'export', name: 'Export' },
]

export const PipelineIndicator: React.FC<PipelineIndicatorProps> = ({
  stages,
  selectedStageNumber = 5,
  onSelectStage,
  runningStageNumber,
}) => {
  // Merge prop stages with defaults
  const stageItems = DEFAULT_STAGES.map((def) => {
    const found = stages?.find((s) => s.stage_number === def.stage_number)
    return (
      found || {
        stage_number: def.stage_number,
        stage_id: def.stage_id,
        name: def.name,
        status: def.stage_number < 5 ? ('completed' as const) : def.stage_number === 5 ? ('ready' as const) : ('disabled' as const),
        is_runnable: def.stage_number <= 7,
        prerequisites_met: def.stage_number <= 5,
        prerequisites_message: def.stage_number > 5 ? 'Pending prior stages' : null,
        description: '',
      }
    )
  })

  return (
    <div className="bg-surface-900 border border-border rounded-xl p-5 shadow-lg">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
        <div>
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
            <span>LandSync Harmonization Pipeline Architecture</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-800">
              14-Stage Workflow
            </span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Click any stage card to inspect inputs, parameters, PostGIS spatial dependencies, and trigger execution.
          </p>
        </div>

        <div className="flex items-center gap-3 text-[11px] font-mono text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" /> Completed
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block" /> Ready
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-slate-500 inline-block" /> Locked
          </span>
        </div>
      </div>

      {/* Grid of 14 stage cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
        {stageItems.map((stage) => {
          const isSelected = selectedStageNumber === stage.stage_number
          const isProcessing = runningStageNumber === stage.stage_number
          const isCompleted = stage.status === 'completed'
          const isReady = stage.status === 'ready'
          const isDisabled = !stage.prerequisites_met && !isCompleted

          return (
            <button
              key={stage.stage_id}
              onClick={() => onSelectStage && onSelectStage(stage.stage_number)}
              title={stage.prerequisites_message || stage.name}
              className={`text-left p-3 rounded-lg border transition-all duration-200 relative group flex flex-col justify-between min-h-[90px] ${
                isSelected
                  ? 'bg-surface-850 border-cyan-500 ring-2 ring-cyan-500/40 shadow-lg shadow-cyan-950/50 -translate-y-0.5'
                  : isCompleted
                  ? 'bg-surface-950/80 border-emerald-900/50 hover:border-emerald-600/80 hover:bg-surface-900 cursor-pointer'
                  : isReady
                  ? 'bg-surface-950/80 border-cyan-900/50 hover:border-cyan-600/80 hover:bg-surface-900 cursor-pointer'
                  : 'bg-surface-950/40 border-border/60 hover:border-slate-700 text-slate-500 cursor-pointer opacity-75'
              }`}
            >
              {/* Header: Number and Status Icon */}
              <div className="flex items-center justify-between text-[11px] font-mono mb-2">
                <span
                  className={`font-bold ${
                    isSelected
                      ? 'text-cyan-300'
                      : isCompleted
                      ? 'text-emerald-400'
                      : isReady
                      ? 'text-cyan-400'
                      : 'text-slate-500'
                  }`}
                >
                  {String(stage.stage_number).padStart(2, '0')}
                </span>

                {isProcessing ? (
                  <span className="flex items-center text-amber-400">
                    <RotateCw className="w-3.5 h-3.5 animate-spin" />
                  </span>
                ) : isCompleted ? (
                  <span className="flex items-center text-emerald-400" title="Completed">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </span>
                ) : isReady ? (
                  <span className="flex items-center text-cyan-400" title="Ready to execute">
                    <Sparkles className="w-3.5 h-3.5" />
                  </span>
                ) : (
                  <span className="flex items-center text-slate-600" title="Prerequisites pending">
                    <Lock className="w-3 h-3" />
                  </span>
                )}
              </div>

              {/* Title */}
              <div
                className={`text-xs font-semibold leading-tight line-clamp-2 ${
                  isSelected
                    ? 'text-cyan-100'
                    : isCompleted
                    ? 'text-slate-200 group-hover:text-emerald-300'
                    : isReady
                    ? 'text-slate-200 group-hover:text-cyan-300'
                    : 'text-slate-400 group-hover:text-slate-300'
                }`}
              >
                {stage.name}
              </div>

              {/* Status footer pill */}
              <div className="mt-2 text-[9px] font-mono">
                {isProcessing ? (
                  <span className="text-amber-400">Running...</span>
                ) : isCompleted ? (
                  <span className="text-emerald-400 font-medium">Completed</span>
                ) : isReady ? (
                  <span className="text-cyan-400 font-medium">Ready</span>
                ) : (
                  <span className="text-slate-600">Locked</span>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
