import React, { useState, useEffect } from 'react'
import {
  X,
  Scale,
  Plane,
  Building,
  Layers,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Loader2,
  FileText,
  User,
  ShieldCheck,
  Ban,
  Sliders,
} from 'lucide-react'
import type { AttributeConflict, ConflictResolveInput, ConflictDismissInput } from '../../types'
import { useResolveConflict, useDismissConflict } from '../../hooks/useConflicts'

interface ConflictResolutionModalProps {
  conflict: AttributeConflict | null
  projectId: string
  recordId: string
  isOpen: boolean
  onClose: () => void
}

export const ConflictResolutionModal: React.FC<ConflictResolutionModalProps> = ({
  conflict,
  projectId,
  recordId,
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'RESOLVE' | 'DISMISS'>('RESOLVE')
  const [resolutionType, setResolutionType] = useState<'SOURCE_SELECTION' | 'MANUAL_VALUE'>('SOURCE_SELECTION')
  const [selectedFeatureId, setSelectedFeatureId] = useState<string>('')
  const [manualValue, setManualValue] = useState<string>('')
  const [comment, setComment] = useState<string>('')
  const [dismissReason, setDismissReason] = useState<string>('')
  const [reviewerName, setReviewerName] = useState<string>('GIS Reviewer')
  const [validationError, setValidationError] = useState<string | null>(null)

  const resolveMutation = useResolveConflict(projectId, recordId)
  const dismissMutation = useDismissConflict(projectId, recordId)

  // Reset form when conflict changes or modal opens
  useEffect(() => {
    if (conflict) {
      if (conflict.detected_values && conflict.detected_values.length > 0) {
        setSelectedFeatureId(conflict.detected_values[0].feature_id)
        setManualValue(String(conflict.detected_values[0].value ?? ''))
      } else {
        setSelectedFeatureId('')
        setManualValue('')
      }
      setResolutionType('SOURCE_SELECTION')
      setActiveTab('RESOLVE')
      setComment(conflict.resolution?.comment || '')
      setDismissReason(conflict.dismissal_reason || '')
      setValidationError(null)
    }
  }, [conflict, isOpen])

  if (!isOpen || !conflict) return null

  const getRoleIcon = (role: string) => {
    switch (role?.toUpperCase()) {
      case 'CADASTRAL':
        return <Scale className="w-3.5 h-3.5 text-cyan-400" />
      case 'DRONE':
        return <Plane className="w-3.5 h-3.5 text-amber-400" />
      case 'MUNICIPAL':
        return <Building className="w-3.5 h-3.5 text-indigo-400" />
      default:
        return <Layers className="w-3.5 h-3.5 text-slate-400" />
    }
  }

  const handleResolve = async (e: React.FormEvent) => {
    e.preventDefault()
    setValidationError(null)

    if (!comment.trim()) {
      setValidationError('A mandatory audit comment is required to record this resolution decision.')
      return
    }

    if (resolutionType === 'SOURCE_SELECTION' && !selectedFeatureId) {
      setValidationError('Please select one of the contributing sources as the canonical authority.')
      return
    }

    if (resolutionType === 'MANUAL_VALUE' && manualValue.trim() === '') {
      setValidationError('Please enter a valid manual value for this attribute.')
      return
    }

    let parsedManualValue: any = manualValue
    if (conflict.conflict_type === 'NUMERIC_DIFFERENCE') {
      const num = Number(manualValue)
      if (!isNaN(num)) {
        parsedManualValue = num
      }
    }

    const input: ConflictResolveInput = {
      resolution_type: resolutionType,
      selected_source_feature_id: resolutionType === 'SOURCE_SELECTION' ? selectedFeatureId : undefined,
      manual_value: resolutionType === 'MANUAL_VALUE' ? parsedManualValue : undefined,
      comment: comment.trim(),
      resolved_by: reviewerName.trim() || 'GIS Reviewer',
    }

    try {
      await resolveMutation.mutateAsync({
        conflictId: conflict.id,
        input,
      })
      onClose()
    } catch {
      // Mutation hook handles error toast
    }
  }

  const handleDismiss = async (e: React.FormEvent) => {
    e.preventDefault()
    setValidationError(null)

    if (!dismissReason.trim()) {
      setValidationError('A mandatory dismissal reason is required to dismiss this conflict.')
      return
    }

    const input: ConflictDismissInput = {
      reason: dismissReason.trim(),
      resolved_by: reviewerName.trim() || 'GIS Reviewer',
    }

    try {
      await dismissMutation.mutateAsync({
        conflictId: conflict.id,
        input,
      })
      onClose()
    } catch {
      // Mutation hook handles error toast
    }
  }

  const isSubmitting = resolveMutation.isPending || dismissMutation.isPending

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-surface-900 border border-border rounded-xl shadow-2xl w-full max-w-xl overflow-hidden flex flex-col font-mono text-xs max-h-[92vh]">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-surface-950/70">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <div>
              <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
                Reconcile Attribute Conflict
              </h2>
              <span className="text-[10px] text-slate-400">
                Attribute: <strong className="text-amber-300 font-mono">{conflict.attribute_name}</strong>
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-surface-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Conflict Overview Info */}
        <div className="px-5 py-3 bg-surface-950/40 border-b border-border/80 flex items-center justify-between text-[11px]">
          <div className="flex items-center gap-3">
            <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-surface-800 text-slate-300 border border-border">
              {conflict.conflict_type.replace(/_/g, ' ')}
            </span>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                conflict.severity === 'HIGH'
                  ? 'bg-red-950 text-red-300 border border-red-700'
                  : conflict.severity === 'MEDIUM'
                  ? 'bg-amber-950 text-amber-300 border border-amber-700'
                  : 'bg-blue-950 text-blue-300 border border-blue-700'
              }`}
            >
              Severity: {conflict.severity}
            </span>
          </div>

          <div className="text-[10px] text-slate-400">
            {conflict.detected_values.length} contributing datasets
          </div>
        </div>

        {/* Action Mode Toggle */}
        <div className="flex border-b border-border bg-surface-950/90 flex-shrink-0">
          <button
            type="button"
            onClick={() => {
              setActiveTab('RESOLVE')
              setValidationError(null)
            }}
            className={`flex-1 py-2.5 text-center text-xs font-bold uppercase tracking-wider transition-colors border-b-2 flex items-center justify-center gap-1.5 ${
              activeTab === 'RESOLVE'
                ? 'border-emerald-400 text-emerald-300 bg-emerald-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Resolve Conflict</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveTab('DISMISS')
              setValidationError(null)
            }}
            className={`flex-1 py-2.5 text-center text-xs font-bold uppercase tracking-wider transition-colors border-b-2 flex items-center justify-center gap-1.5 ${
              activeTab === 'DISMISS'
                ? 'border-slate-400 text-slate-200 bg-surface-850'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Ban className="w-3.5 h-3.5 text-slate-400" />
            <span>Dismiss (Accept Variance)</span>
          </button>
        </div>

        {/* Modal Body Form */}
        <div className="p-5 overflow-y-auto space-y-4">
          {validationError && (
            <div className="p-3 rounded-lg bg-red-950/80 border border-red-700 text-red-200 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
              <span>{validationError}</span>
            </div>
          )}

          {activeTab === 'RESOLVE' ? (
            <form id="conflict-resolve-form" onSubmit={handleResolve} className="space-y-4">
              {/* Evidence Selection */}
              <div className="space-y-2">
                <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Cross-Dataset Evidence Comparison</span>
                </label>
                <p className="text-[10px] text-slate-400">
                  Select a contributing source to establish canonical truth, or specify a manual verified value.
                </p>

                <div className="space-y-2 pt-1">
                  {conflict.detected_values.map((dv) => {
                    const isSelected =
                      resolutionType === 'SOURCE_SELECTION' && selectedFeatureId === dv.feature_id
                    return (
                      <div
                        key={dv.feature_id}
                        onClick={() => {
                          setResolutionType('SOURCE_SELECTION')
                          setSelectedFeatureId(dv.feature_id)
                          setManualValue(String(dv.value ?? ''))
                        }}
                        className={`p-3 rounded-lg border cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-emerald-950/40 border-emerald-500 shadow-sm'
                            : 'bg-surface-950/70 border-border hover:border-slate-500'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-2">
                            <input
                              type="radio"
                              name="source_selection"
                              checked={isSelected}
                              onChange={() => {
                                setResolutionType('SOURCE_SELECTION')
                                setSelectedFeatureId(dv.feature_id)
                                setManualValue(String(dv.value ?? ''))
                              }}
                              className="text-emerald-500 bg-surface-900 border-border focus:ring-emerald-500"
                            />
                            <div className="flex items-center gap-1.5">
                              {getRoleIcon(dv.source_role)}
                              <span className="font-bold text-slate-200 text-xs">
                                {dv.source_role}
                              </span>
                            </div>
                            <span className="text-[10px] text-slate-400 font-mono">
                              ({dv.dataset_name} v{dv.dataset_version})
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">
                            ID: {dv.feature_identifier}
                          </span>
                        </div>

                        <div className="mt-2 pl-6 flex items-center justify-between">
                          <span className="text-[10px] text-slate-400">Reported Value:</span>
                          <span className="font-mono font-bold text-sm text-amber-300 bg-surface-900 px-2 py-0.5 rounded border border-border/60">
                            {dv.value !== null && dv.value !== undefined ? String(dv.value) : 'NULL'}
                          </span>
                        </div>
                      </div>
                    )
                  })}

                  {/* Manual Value Option */}
                  <div
                    onClick={() => setResolutionType('MANUAL_VALUE')}
                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                      resolutionType === 'MANUAL_VALUE'
                        ? 'bg-cyan-950/40 border-cyan-500 shadow-sm'
                        : 'bg-surface-950/70 border-border hover:border-slate-500'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <input
                        type="radio"
                        name="source_selection"
                        checked={resolutionType === 'MANUAL_VALUE'}
                        onChange={() => setResolutionType('MANUAL_VALUE')}
                        className="text-cyan-500 bg-surface-900 border-border focus:ring-cyan-500"
                      />
                      <span className="font-bold text-slate-200 text-xs">
                        Manual Expert Reconciliation
                      </span>
                      <span className="text-[10px] text-cyan-400">
                        (Custom override from surveyed ground truth)
                      </span>
                    </div>

                    <div className="pl-6">
                      <input
                        type="text"
                        value={manualValue}
                        onChange={(e) => {
                          setManualValue(e.target.value)
                          if (resolutionType !== 'MANUAL_VALUE') {
                            setResolutionType('MANUAL_VALUE')
                          }
                        }}
                        placeholder={`Enter verified canonical ${conflict.attribute_name}...`}
                        className="w-full px-3 py-1.5 rounded bg-surface-900 border border-border text-slate-200 font-mono text-xs focus:outline-none focus:border-cyan-500"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Reviewer & Audit Details */}
              <div className="space-y-3 pt-2 border-t border-border">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                      Reviewer Identifier
                    </label>
                    <div className="flex items-center gap-2 bg-surface-950 px-2.5 py-1.5 rounded border border-border">
                      <User className="w-3.5 h-3.5 text-slate-500" />
                      <input
                        type="text"
                        value={reviewerName}
                        onChange={(e) => setReviewerName(e.target.value)}
                        placeholder="Reviewer Name"
                        className="bg-transparent border-none text-slate-200 text-xs focus:outline-none w-full"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                      Resolution Strategy
                    </label>
                    <div className="px-2.5 py-1.5 rounded bg-surface-950 border border-border text-slate-300 text-xs font-mono">
                      {resolutionType}
                    </div>
                  </div>
                </div>

                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                    Mandatory Audit Note / Justification *
                  </label>
                  <textarea
                    rows={2}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Document the empirical evidence or operational rationale for this resolution..."
                    className="w-full px-3 py-2 rounded bg-surface-950 border border-border text-slate-200 font-mono text-xs focus:outline-none focus:border-emerald-500 resize-none"
                  />
                  <span className="text-[9px] text-slate-500 block">
                    All resolution actions are permanently appended to the immutable provenance audit trail.
                  </span>
                </div>
              </div>
            </form>
          ) : (
            <form id="conflict-dismiss-form" onSubmit={handleDismiss} className="space-y-4">
              <div className="p-3 rounded-lg bg-surface-950 border border-border space-y-2">
                <div className="flex items-center gap-2 text-slate-200 font-bold">
                  <Ban className="w-4 h-4 text-slate-400" />
                  <span>Dismiss Conflict (Tolerable Variance)</span>
                </div>
                <p className="text-[10px] text-slate-400 leading-relaxed">
                  Dismissing this conflict acknowledges the discrepancy between datasets without forcing a canonical override. The record will be unblocked if no other material conflicts exist.
                </p>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                  Reviewer Identifier
                </label>
                <div className="flex items-center gap-2 bg-surface-950 px-2.5 py-1.5 rounded border border-border">
                  <User className="w-3.5 h-3.5 text-slate-500" />
                  <input
                    type="text"
                    value={reviewerName}
                    onChange={(e) => setReviewerName(e.target.value)}
                    placeholder="Reviewer Name"
                    className="bg-transparent border-none text-slate-200 text-xs focus:outline-none w-full"
                  />
                </div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                  Mandatory Dismissal Reason *
                </label>
                <textarea
                  rows={3}
                  value={dismissReason}
                  onChange={(e) => setDismissReason(e.target.value)}
                  placeholder="Explain why this attribute variance is acceptable (e.g. minor semantic nuance, non-critical field)..."
                  className="w-full px-3 py-2 rounded bg-surface-950 border border-border text-slate-200 font-mono text-xs focus:outline-none focus:border-slate-400 resize-none"
                />
              </div>
            </form>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-3 border-t border-border bg-surface-950/70 flex items-center justify-between flex-shrink-0">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-3 py-1.5 rounded text-xs text-slate-400 hover:text-slate-200 hover:bg-surface-850 transition-colors"
          >
            Cancel
          </button>

          {activeTab === 'RESOLVE' ? (
            <button
              type="submit"
              form="conflict-resolve-form"
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-surface-950 font-bold text-xs shadow-md transition-all active:scale-[0.98] disabled:opacity-50"
            >
              {isSubmitting ? (
                <Loader2 className="w-4 h-4 animate-spin text-surface-950" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
              <span>Apply Canonical Resolution</span>
            </button>
          ) : (
            <button
              type="submit"
              form="conflict-dismiss-form"
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white font-bold text-xs shadow-md transition-all active:scale-[0.98] disabled:opacity-50"
            >
              {isSubmitting ? (
                <Loader2 className="w-4 h-4 animate-spin text-white" />
              ) : (
                <Ban className="w-4 h-4" />
              )}
              <span>Confirm Dismissal</span>
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
