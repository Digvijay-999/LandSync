import React from 'react'
import { CheckCircle2, Clock, CircleDot, ArrowRight } from 'lucide-react'

export interface PipelineStep {
  id: string
  label: string
  stageNumber: number
  status: 'foundation_ready' | 'pending_milestone' | 'active'
}

export const PIPELINE_STAGES: PipelineStep[] = [
  { id: 'ingestion', label: 'Data Ingestion', stageNumber: 1, status: 'pending_milestone' },
  { id: 'profiling', label: 'Data Profiling', stageNumber: 2, status: 'pending_milestone' },
  { id: 'crs', label: 'CRS Normalization', stageNumber: 3, status: 'pending_milestone' },
  { id: 'schema', label: 'Schema Normalization', stageNumber: 4, status: 'pending_milestone' },
  { id: 'candidate', label: 'Spatial Candidate Gen', stageNumber: 5, status: 'pending_milestone' },
  { id: 'matching', label: 'Feature Matching', stageNumber: 6, status: 'pending_milestone' },
  { id: 'harmonization', label: 'Attr/Geom Harmonization', stageNumber: 7, status: 'pending_milestone' },
  { id: 'conflict', label: 'Conflict Detection', stageNumber: 8, status: 'pending_milestone' },
  { id: 'validation', label: 'Validation', stageNumber: 9, status: 'pending_milestone' },
  { id: 'scoring', label: 'Confidence Scoring', stageNumber: 10, status: 'pending_milestone' },
  { id: 'review', label: 'Human Review', stageNumber: 11, status: 'pending_milestone' },
  { id: 'record', label: 'Unified Record', stageNumber: 12, status: 'pending_milestone' },
  { id: 'provenance', label: 'Provenance', stageNumber: 13, status: 'pending_milestone' },
  { id: 'export', label: 'Export', stageNumber: 14, status: 'pending_milestone' },
]

export const PipelineIndicator: React.FC = () => {
  return (
    <div className="bg-surface-900 border border-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider font-mono flex items-center gap-2">
            <span>LandSync Harmonization Pipeline Architecture</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800">
              14-Stage Pipeline
            </span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Foundation milestone establishes core persistence, API contract, and PostGIS storage. Processing modules plug into this pipeline.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
        {PIPELINE_STAGES.map((stage, idx) => (
          <div
            key={stage.id}
            className="p-3 rounded border border-border/80 bg-surface-950/60 flex flex-col justify-between hover:border-slate-700 transition-colors"
          >
            <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 mb-1">
              <span>{String(stage.stageNumber).padStart(2, '0')}</span>
              <span className="flex items-center gap-1 text-[10px] text-slate-400">
                <Clock className="w-3 h-3 text-slate-400" />
                <span>Next Milestone</span>
              </span>
            </div>
            <div className="text-xs font-medium text-slate-300 truncate" title={stage.label}>
              {stage.label}
            </div>
            {idx < PIPELINE_STAGES.length - 1 && (
              <div className="hidden lg:block absolute right-0 top-1/2" />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
