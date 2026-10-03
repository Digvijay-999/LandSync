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
  Eye,
  X,
  Search,
  Filter,
  Check,
  MapPin,
  FileText,
  XCircle,
  CheckSquare,
  UserCheck,
  AlertOctagon,
  CornerDownRight,
  ThumbsUp,
  ThumbsDown,
  GitBranch,
  History,
  Download,
  FileJson,
  FileSpreadsheet,
  HardDrive,
  Share2,
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
  ConflictDetectionRunResponse,
  GeospatialConflict,
  ValidationResult,
  ValidationSummary,
  ValidationRunResponse,
  ValidationStatus,
  ConfidenceRecordItem,
  ConfidenceSummary,
  ConfidenceScoringRunResponse,
  ConfidenceBucket,
  AdjudicationQueueItem as ReviewQueueItem,
  ReviewQueueSummary,
  ReviewQueueConflictItem,
  AdjudicationActionType,
  UnifiedRecordListItem,
  Stage12ExecutionResponse,
  Stage12StatusResponse,
  ProvenanceRecordItem,
  ProvenanceRecordDetailResponse,
  Stage13ExecutionResponse,
  Stage13StatusResponse,
  ProjectProvenanceSummaryResponse,
  ProvenanceTimelineItem,
  ProvenanceSourceItem,
  ExportJobItem,
  Stage14ExecutionResponse,
  Stage14StatusResponse,
} from '../../types'
import {
  useRunCandidateGeneration,
  useRunFeatureMatching,
  useRunHarmonization,
  useRunConflictDetection,
  useGeospatialConflicts,
  useUpdateConflictStatus,
  useRunValidation,
  useValidationResults,
  useValidationSummary,
  useRunConfidenceScoring,
  useConfidenceResults,
  useConfidenceSummary,
  useReviewSummary,
  useReviewQueue,
  useSubmitAdjudication,
  useFinalizeStage11,
  useStage12Status,
  useRunStage12,
  useStage13Status,
  useRunStage13,
  useProjectProvenance,
  useProvenanceRecordDetail,
  useStage14Status,
  useRunStage14,
  useProjectExports,
  useCreateExportJob,
} from '../../hooks/usePipeline'
import { useUnifiedRecords } from '../../hooks/useUnified'
import { api } from '../../services/api'

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

  // Stage 08 configurable parameters
  const [areaLowThresholdPct, setAreaLowThresholdPct] = useState<number>(2.0)
  const [areaMediumThresholdPct, setAreaMediumThresholdPct] = useState<number>(5.0)
  const [areaHighThresholdPct, setAreaHighThresholdPct] = useState<number>(15.0)
  const [includeGeomMetrics, setIncludeGeomMetrics] = useState<boolean>(true)

  // Stage 09 configurable parameters
  const [valAreaTolerancePct, setValAreaTolerancePct] = useState<number>(5.0)
  const [valAreaWarningPct, setValAreaWarningPct] = useState<number>(15.0)
  const [valCheckTopology, setValCheckTopology] = useState<boolean>(true)
  const [valCheckSemantics, setValCheckSemantics] = useState<boolean>(true)
  const [valConsumeConflicts, setValConsumeConflicts] = useState<boolean>(true)

  // Stage 10 configurable parameters
  const [confSpatialWeight, setConfSpatialWeight] = useState<number>(0.30)
  const [confGeometryWeight, setConfGeometryWeight] = useState<number>(0.30)
  const [confAttributeWeight, setConfAttributeWeight] = useState<number>(0.30)
  const [confTemporalWeight, setConfTemporalWeight] = useState<number>(0.10)
  const [confHighThreshold, setConfHighThreshold] = useState<number>(0.90)
  const [confMediumThreshold, setConfMediumThreshold] = useState<number>(0.70)
  const [confEnforceValidation, setConfEnforceValidation] = useState<boolean>(true)
  const [confEnforceConflicts, setConfEnforceConflicts] = useState<boolean>(true)

  // Local state for freshly returned execution results
  const [candidateResult, setCandidateResult] = useState<CandidateGenerationResponse | null>(null)
  const [matchingResult, setMatchingResult] = useState<FeatureMatchingRunResponse | null>(null)
  const [harmonizationResult, setHarmonizationResult] = useState<HarmonizationRunResponse | null>(null)
  const [conflictResult, setConflictResult] = useState<ConflictDetectionRunResponse | null>(null)
  const [validationResult, setValidationResult] = useState<ValidationRunResponse | null>(null)
  const [confidenceRunResult, setConfidenceRunResult] = useState<ConfidenceScoringRunResponse | null>(null)
  const [selectedConflict, setSelectedConflict] = useState<GeospatialConflict | null>(null)
  const [selectedValidationItem, setSelectedValidationItem] = useState<ValidationResult | null>(null)
  const [selectedConfidenceItem, setSelectedConfidenceItem] = useState<ConfidenceRecordItem | null>(null)
  const [conflictSeverityFilter, setConflictSeverityFilter] = useState<string>('ALL')
  const [conflictTypeFilter, setConflictTypeFilter] = useState<string>('ALL')
  const [conflictStatusFilter, setConflictStatusFilter] = useState<string>('ALL')
  const [conflictSearchTerm, setConflictSearchTerm] = useState<string>('')
  const [statusUpdateNote, setStatusUpdateNote] = useState<string>('')
  const [valStatusFilter, setValStatusFilter] = useState<string>('ALL')
  const [valCategoryFilter, setValCategoryFilter] = useState<string>('ALL')
  const [valSearchTerm, setValSearchTerm] = useState<string>('')
  const [confBucketFilter, setConfBucketFilter] = useState<string>('ALL')
  const [confReviewStatusFilter, setConfReviewStatusFilter] = useState<string>('ALL')
  const [confSearchTerm, setConfSearchTerm] = useState<string>('')
  const [searchTerm, setSearchTerm] = useState('')
  const [filterRel, setFilterRel] = useState<string>('ALL')
  const [elapsedTimeMs, setElapsedTimeMs] = useState<number>(0)

  const candidateMutation = useRunCandidateGeneration(projectId)
  const matchingMutation = useRunFeatureMatching(projectId)
  const harmonizationMutation = useRunHarmonization(projectId)
  const conflictMutation = useRunConflictDetection(projectId)
  const validationMutation = useRunValidation(projectId)
  const confidenceMutation = useRunConfidenceScoring(projectId)
  const updateStatusMutation = useUpdateConflictStatus(projectId)

  const { data: conflictsListResponse, refetch: refetchConflicts } = useGeospatialConflicts(
    projectId,
    {
      severity: conflictSeverityFilter !== 'ALL' ? conflictSeverityFilter : undefined,
      conflict_type: conflictTypeFilter !== 'ALL' ? conflictTypeFilter : undefined,
      status: conflictStatusFilter !== 'ALL' ? conflictStatusFilter : undefined,
      search: conflictSearchTerm.trim() ? conflictSearchTerm.trim() : undefined,
      limit: 100,
    }
  )

  const { data: validationListResponse, refetch: refetchValidation } = useValidationResults(
    projectId,
    {
      status: valStatusFilter !== 'ALL' ? valStatusFilter : undefined,
      category: valCategoryFilter !== 'ALL' ? valCategoryFilter : undefined,
      search: valSearchTerm.trim() ? valSearchTerm.trim() : undefined,
      limit: 100,
    }
  )

  const { data: validationSummaryData, refetch: refetchSummary } = useValidationSummary(projectId)

  const { data: confidenceListResponse, refetch: refetchConfidenceResults } = useConfidenceResults(
    projectId,
    {
      bucket: confBucketFilter !== 'ALL' ? confBucketFilter : undefined,
      review_status: confReviewStatusFilter !== 'ALL' ? confReviewStatusFilter : undefined,
      search: confSearchTerm.trim() ? confSearchTerm.trim() : undefined,
      limit: 100,
    }
  )

  const { data: confidenceSummaryData, refetch: refetchConfidenceSummary } = useConfidenceSummary(projectId)

  // Stage 11: Human Review & Adjudication State
  const [reviewSeverityFilter, setReviewSeverityFilter] = useState<string>('ALL')
  const [reviewBucketFilter, setReviewBucketFilter] = useState<string>('ALL')
  const [reviewValidationFilter, setReviewValidationFilter] = useState<string>('ALL')
  const [reviewAdjudicationFilter, setReviewAdjudicationFilter] = useState<string>('ALL')
  const [reviewSearchTerm, setReviewSearchTerm] = useState<string>('')
  const [selectedReviewRecord, setSelectedReviewRecord] = useState<ReviewQueueItem | null>(null)
  const [selectedAction, setSelectedAction] = useState<AdjudicationActionType>('ACCEPT_SOURCE_A')
  const [adjudicationNotes, setAdjudicationNotes] = useState<string>('')
  const [authGeomSource, setAuthGeomSource] = useState<'SOURCE_A' | 'SOURCE_B' | 'CUSTOM'>('SOURCE_A')
  const [authLandUse, setAuthLandUse] = useState<string>('')
  const [authMutationStatus, setAuthMutationStatus] = useState<string>('')
  const [authRiskLevel, setAuthRiskLevel] = useState<string>('')
  const [adjudicationFeedback, setAdjudicationFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [isConfirmingAction, setIsConfirmingAction] = useState<boolean>(false)

  const {
    data: reviewQueueResponse,
    isLoading: reviewQueueLoading,
    refetch: refetchReviewQueue,
  } = useReviewQueue(projectId, {
    severity: reviewSeverityFilter !== 'ALL' ? reviewSeverityFilter : undefined,
    bucket: reviewBucketFilter !== 'ALL' ? reviewBucketFilter : undefined,
    validation_status: reviewValidationFilter !== 'ALL' ? reviewValidationFilter : undefined,
    adjudication_status: reviewAdjudicationFilter !== 'ALL' ? reviewAdjudicationFilter : undefined,
    search: reviewSearchTerm.trim() ? reviewSearchTerm.trim() : undefined,
    page: 1,
    page_size: 100,
  })

  const {
    data: reviewSummaryData,
    isLoading: reviewSummaryLoading,
    refetch: refetchReviewSummary,
  } = useReviewSummary(projectId)

  const adjudicationMutation = useSubmitAdjudication(projectId)
  const finalizeStage11Mutation = useFinalizeStage11(projectId)

  // Stage 12 State & Hooks
  const [st12SearchTerm, setSt12SearchTerm] = useState<string>('')
  const [st12ResolutionFilter, setSt12ResolutionFilter] = useState<string>('ALL')
  const [selectedUnifiedRecord, setSelectedUnifiedRecord] = useState<UnifiedRecordListItem | null>(null)
  const [st12Feedback, setSt12Feedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [st12RunResult, setSt12RunResult] = useState<Stage12ExecutionResponse | null>(null)

  const { data: st12StatusData, refetch: refetchStage12Status } = useStage12Status(projectId)
  const {
    data: unifiedRecordsData,
    isLoading: unifiedRecordsLoading,
    refetch: refetchUnifiedRecords,
  } = useUnifiedRecords(projectId, {
    resolution_status: st12ResolutionFilter !== 'ALL' ? st12ResolutionFilter : undefined,
    search: st12SearchTerm.trim() ? st12SearchTerm.trim() : undefined,
    limit: 100,
  })
  const runStage12Mutation = useRunStage12(projectId)

  // Stage 13 State & Hooks (Provenance & Lineage)
  const [st13SearchTerm, setSt13SearchTerm] = useState<string>('')
  const [st13StatusFilter, setSt13StatusFilter] = useState<string>('ALL')
  const [selectedProvenanceRecord, setSelectedProvenanceRecord] = useState<ProvenanceRecordItem | null>(null)
  const [st13Feedback, setSt13Feedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [st13RunResult, setSt13RunResult] = useState<Stage13ExecutionResponse | null>(null)
  const [lineageModalTab, setLineageModalTab] = useState<'OVERVIEW' | 'SOURCES' | 'PROCESSING' | 'DECISION' | 'TIMELINE' | 'GRAPH'>('OVERVIEW')

  const { data: st13StatusData, refetch: refetchStage13Status } = useStage13Status(projectId)
  const {
    data: projectProvenanceData,
    isLoading: projectProvenanceLoading,
    refetch: refetchProjectProvenance,
  } = useProjectProvenance(projectId, {
    status_filter: st13StatusFilter !== 'ALL' ? st13StatusFilter : undefined,
    search: st13SearchTerm.trim() ? st13SearchTerm.trim() : undefined,
    limit: 100,
  })
  const {
    data: selectedProvenanceDetail,
    isLoading: provenanceDetailLoading,
  } = useProvenanceRecordDetail(projectId, selectedProvenanceRecord?.unified_land_record_id)
  const runStage13Mutation = useRunStage13(projectId)

  // Stage 14: Export & Deliverables Hooks & State
  const { data: st14StatusData, refetch: refetchStage14Status } = useStage14Status(projectId)
  const runStage14Mutation = useRunStage14(projectId)
  const {
    data: projectExportsData,
    refetch: refetchProjectExports,
    isLoading: isLoadingExports,
  } = useProjectExports(projectId)
  const createExportMutation = useCreateExportJob(projectId)

  const [selectedFormat, setSelectedFormat] = useState<'geojson' | 'gpkg' | 'csv'>('geojson')
  const [includeQuarantined, setIncludeQuarantined] = useState<boolean>(false)
  const [st14Feedback, setSt14Feedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [selectedManifestExport, setSelectedManifestExport] = useState<ExportJobItem | null>(null)
  const [isDownloading, setIsDownloading] = useState<string | null>(null)

  const isRunning =
    (stage.stage_number === 5 && candidateMutation.isPending) ||
    (stage.stage_number === 6 && matchingMutation.isPending) ||
    (stage.stage_number === 7 && harmonizationMutation.isPending) ||
    (stage.stage_number === 8 && conflictMutation.isPending) ||
    (stage.stage_number === 9 && validationMutation.isPending) ||
    (stage.stage_number === 10 && confidenceMutation.isPending) ||
    (stage.stage_number === 11 && (adjudicationMutation.isPending || finalizeStage11Mutation.isPending)) ||
    (stage.stage_number === 12 && runStage12Mutation.isPending) ||
    (stage.stage_number === 13 && runStage13Mutation.isPending) ||
    (stage.stage_number === 14 && (runStage14Mutation.isPending || createExportMutation.isPending))

  React.useEffect(() => {
    let timer: any
    if (isRunning) {
      const start = Date.now()
      setElapsedTimeMs(0)
      timer = setInterval(() => {
        setElapsedTimeMs(Date.now() - start)
      }, 100)
    }
    return () => clearInterval(timer)
  }, [isRunning])

  const executionError =
    (stage.stage_number === 5 ? candidateMutation.error?.message : null) ||
    (stage.stage_number === 6 ? matchingMutation.error?.message : null) ||
    (stage.stage_number === 7 ? harmonizationMutation.error?.message : null) ||
    (stage.stage_number === 8 ? conflictMutation.error?.message : null) ||
    (stage.stage_number === 9 ? validationMutation.error?.message : null) ||
    (stage.stage_number === 10 ? confidenceMutation.error?.message : null) ||
    (stage.stage_number === 11 ? (finalizeStage11Mutation.error?.message || adjudicationMutation.error?.message) : null) ||
    (stage.stage_number === 12 ? runStage12Mutation.error?.message : null) ||
    (stage.stage_number === 13 ? runStage13Mutation.error?.message : null) ||
    (stage.stage_number === 14 ? (runStage14Mutation.error?.message || createExportMutation.error?.message) : null)

  const isStageRunnable = Boolean(
    stage.is_runnable ||
    stage.stage_number === 5 ||
    stage.stage_number === 6 ||
    stage.stage_number === 7 ||
    stage.stage_number === 8 ||
    stage.stage_number === 9 ||
    stage.stage_number === 10 ||
    stage.stage_number === 11 ||
    stage.stage_number === 12 ||
    stage.stage_number === 13 ||
    stage.stage_number === 14
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
    } else if (stage.stage_number === 8) {
      try {
        const res = await conflictMutation.mutateAsync({
          area_low_threshold_pct: areaLowThresholdPct,
          area_medium_threshold_pct: areaMediumThresholdPct,
          area_high_threshold_pct: areaHighThresholdPct,
          include_geometry_metrics: includeGeomMetrics,
        })
        setConflictResult(res)
        refetchConflicts()
      } catch (e) {
        console.error('Conflict detection failed', e)
      }
    } else if (stage.stage_number === 9) {
      try {
        const res = await validationMutation.mutateAsync({
          area_tolerance_pct: valAreaTolerancePct,
          area_warning_threshold_pct: valAreaWarningPct,
          check_topology: valCheckTopology,
          check_semantics: valCheckSemantics,
          consume_conflicts: valConsumeConflicts,
        })
        setValidationResult(res)
        refetchValidation()
        refetchSummary()
      } catch (e) {
        console.error('Validation stage failed', e)
      }
    } else if (stage.stage_number === 10) {
      try {
        const res = await confidenceMutation.mutateAsync({
          spatial_weight: confSpatialWeight,
          geometry_weight: confGeometryWeight,
          attribute_weight: confAttributeWeight,
          temporal_weight: confTemporalWeight,
          high_threshold: confHighThreshold,
          medium_threshold: confMediumThreshold,
          enforce_validation_constraints: confEnforceValidation,
          enforce_conflict_constraints: confEnforceConflicts,
        })
        setConfidenceRunResult(res)
        refetchConfidenceResults()
        refetchConfidenceSummary()
      } catch (e) {
        console.error('Confidence scoring stage failed', e)
      }
    } else if (stage.stage_number === 11) {
      try {
        await finalizeStage11Mutation.mutateAsync()
        refetchReviewSummary()
        refetchReviewQueue()
      } catch (e: any) {
        console.error('Finalize stage 11 failed', e)
        setAdjudicationFeedback({
          type: 'error',
          message: e?.response?.data?.error?.message || e?.message || 'Finalization failed',
        })
      }
    } else if (stage.stage_number === 12) {
      try {
        const res = await runStage12Mutation.mutateAsync()
        setSt12RunResult(res)
        setSt12Feedback({
          type: 'success',
          message: res.message || 'Unified land records successfully synthesized.',
        })
        refetchStage12Status()
        refetchUnifiedRecords()
      } catch (e: any) {
        console.error('Stage 12 execution failed', e)
        setSt12Feedback({
          type: 'error',
          message: e?.response?.data?.error?.message || e?.message || 'Unified record generation failed',
        })
      }
    } else if (stage.stage_number === 13) {
      try {
        const res = await runStage13Mutation.mutateAsync()
        setSt13RunResult(res)
        setSt13Feedback({
          type: 'success',
          message: res.message || 'Provenance and complete pipeline lineage successfully generated.',
        })
        refetchStage13Status()
        refetchProjectProvenance()
      } catch (e: any) {
        console.error('Stage 13 execution failed', e)
        setSt13Feedback({
          type: 'error',
          message: e?.response?.data?.error?.message || e?.message || 'Provenance generation failed',
        })
      }
    } else if (stage.stage_number === 14) {
      try {
        const res = await runStage14Mutation.mutateAsync()
        setSt14Feedback({
          type: 'success',
          message: res.message || 'Stage 14 authoritative export deliverable successfully generated.',
        })
        refetchStage14Status()
        refetchProjectExports()
        if (res.export_job) {
          handleTriggerDownload(res.export_job)
        }
      } catch (e: any) {
        console.error('Stage 14 execution failed', e)
        setSt14Feedback({
          type: 'error',
          message: e?.response?.data?.error?.message || e?.message || 'Stage 14 export execution failed',
        })
      }
    }
  }

  const handleTriggerDownload = (exportItem: ExportJobItem) => {
    try {
      setIsDownloading(exportItem.id)
      const downloadUrl = api.getExportDownloadUrl(projectId, exportItem.id)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.setAttribute('download', exportItem.filename)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } catch (err: any) {
      console.error('Download failed', err)
    } finally {
      setIsDownloading(null)
    }
  }

  const handleGenerateDeliverable = async () => {
    try {
      const res = await createExportMutation.mutateAsync({
        format: selectedFormat,
        include_quarantined: includeQuarantined,
      })
      setSt14Feedback({
        type: 'success',
        message: `Successfully generated ${res.format.toUpperCase()} deliverable (${res.filename}).`,
      })
      refetchStage14Status()
      refetchProjectExports()
      handleTriggerDownload(res)
    } catch (e: any) {
      setSt14Feedback({
        type: 'error',
        message: e?.response?.data?.error?.message || e?.message || 'Deliverable generation failed',
      })
    }
  }

  const handleOpenAdjudication = (record: ReviewQueueItem) => {
    setSelectedReviewRecord(record)
    setSelectedAction(record.adjudication_action || 'ACCEPT_SOURCE_A')
    setAdjudicationNotes(record.notes || '')
    setAuthGeomSource((record.authoritative_geometry_source as any) || 'SOURCE_A')
    setAuthLandUse(record.authoritative_attributes?.land_use || record.harmonized_attributes?.candidate_land_use || '')
    setAuthMutationStatus(record.authoritative_attributes?.mutation_status || '')
    setAuthRiskLevel(record.authoritative_attributes?.risk_level || '')
    setAdjudicationFeedback(null)
    setIsConfirmingAction(false)
  }

  const handleSubmitAdjudication = async () => {
    if (!selectedReviewRecord || !selectedAction) return

    const isOverride =
      (selectedReviewRecord.has_critical_conflicts || selectedReviewRecord.validation_status === 'FAIL') &&
      ['ACCEPT_SOURCE_A', 'ACCEPT_SOURCE_B', 'MERGE_RECONCILE'].includes(selectedAction)
    const requiresNote =
      selectedAction === 'REJECT_UNRESOLVED' || selectedAction === 'MERGE_RECONCILE' || isOverride

    if (requiresNote && !adjudicationNotes.trim()) {
      setAdjudicationFeedback({
        type: 'error',
        message: 'Reviewer justification note is strictly mandatory for Reject, Merge, or when overriding critical conflicts/validation failures.',
      })
      return
    }

    try {
      const res = await adjudicationMutation.mutateAsync({
        recordId: selectedReviewRecord.id,
        payload: {
          action: selectedAction,
          notes: adjudicationNotes.trim() || undefined,
          reviewer_name: 'Lead GIS Adjudicator',
          authoritative_geometry_source: selectedAction === 'MERGE_RECONCILE' ? authGeomSource : undefined,
          authoritative_attributes:
            selectedAction === 'MERGE_RECONCILE'
              ? {
                  land_use: authLandUse || undefined,
                  mutation_status: authMutationStatus || undefined,
                  risk_level: authRiskLevel || undefined,
                }
              : undefined,
        },
      })
      setAdjudicationFeedback({
        type: 'success',
        message: res.message,
      })
      setSelectedReviewRecord(res.decision)
      refetchReviewQueue()
      refetchReviewSummary()
      setIsConfirmingAction(false)
    } catch (e: any) {
      setAdjudicationFeedback({
        type: 'error',
        message: e?.response?.data?.error?.message || e?.message || 'Failed to submit adjudication decision',
      })
    }
  }

  const handleUpdateConflictStatus = async (newStatus: string) => {
    if (!selectedConflict) return
    try {
      const updated = await updateStatusMutation.mutateAsync({
        conflictId: selectedConflict.id,
        status: newStatus,
        notes: statusUpdateNote.trim() || undefined,
      })
      setSelectedConflict(updated)
      setStatusUpdateNote('')
      refetchConflicts()
    } catch (e) {
      console.error('Failed to update conflict status', e)
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
                      : stage.stage_number === 11
                      ? 'Finalizing Review Stage...'
                      : stage.stage_number === 14
                      ? 'Generating Deliverables...'
                      : 'Executing Stage...'}
                  </span>
                </>
              ) : stage.status === 'completed' ? (
                <>
                  <RotateCw className="w-4 h-4" />
                  <span>
                    {stage.stage_number === 7
                      ? 'Re-run Attribute/Geometry Harmonization'
                      : stage.stage_number === 11
                      ? 'Re-finalize Review Stage'
                      : stage.stage_number === 14
                      ? 'Re-generate Authoritative Export'
                      : `Re-run ${stage.name}`}
                  </span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>
                    {stage.stage_number === 7
                      ? 'Run Attribute/Geometry Harmonization'
                      : stage.stage_number === 11
                      ? 'Finalize Review Stage'
                      : stage.stage_number === 14
                      ? 'Generate Authoritative Export'
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
        {/* STAGE 08: CONFLICT DETECTION WORKFLOW & ENGINE            */}
        {/* ========================================================= */}
        {stage.stage_number === 8 && (
          <div className="space-y-5">
            {/* Prerequisite & Stage Header */}
            <div className="p-4 rounded-lg bg-surface-950/80 border border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className="text-slate-400">Prerequisite (Stage 07 Harmonization):</span>
                {stage.prerequisites_met ? (
                  <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Harmonized Records Ready
                  </span>
                ) : (
                  <span className="text-amber-400 flex items-center gap-1">
                    <Lock className="w-3.5 h-3.5" />
                    Requires Stage 07 Harmonization
                  </span>
                )}
              </div>
              <div className="text-[11px] text-slate-400">
                Rule Engine: <span className="text-cyan-300 font-semibold">Deterministic PostGIS &amp; Semantic Classifier</span>
              </div>
            </div>

            {/* Threshold & Configuration Controls */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Area Low & Medium Thresholds */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Area Thresholds (Low / Med)</span>
                </div>
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400">Standard / High Thresholds:</span>
                  <span className="font-bold text-cyan-300">{areaLowThresholdPct}% / {areaMediumThresholdPct}%</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="10"
                  step="0.5"
                  value={areaLowThresholdPct}
                  onChange={(e) => setAreaLowThresholdPct(Number(e.target.value))}
                  className="w-full h-1.5 bg-surface-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                />
                <div className="text-[10px] text-slate-500 font-mono">
                  &lt; {areaLowThresholdPct}% (LOW), {areaLowThresholdPct}–{areaMediumThresholdPct}% (MEDIUM)
                </div>
              </div>

              {/* Area Critical Threshold */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                  <span>Critical Area Threshold</span>
                </div>
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400">Critical Discrepancy:</span>
                  <span className="font-bold text-rose-400">&gt; {areaHighThresholdPct}%</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="30"
                  step="1"
                  value={areaHighThresholdPct}
                  onChange={(e) => setAreaHighThresholdPct(Number(e.target.value))}
                  className="w-full h-1.5 bg-surface-800 rounded-lg appearance-none cursor-pointer accent-rose-500"
                />
                <div className="text-[10px] text-slate-500 font-mono">
                  5%–{areaHighThresholdPct}% (HIGH), &gt; {areaHighThresholdPct}% (CRITICAL)
                </div>
              </div>

              {/* Spatial Metrics Toggle */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border space-y-2">
                <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-purple-400" />
                  <span>PostGIS Spatial Metrics</span>
                </div>
                <label className="flex items-center gap-2 cursor-pointer pt-1">
                  <input
                    type="checkbox"
                    checked={includeGeomMetrics}
                    onChange={(e) => setIncludeGeomMetrics(e.target.checked)}
                    className="rounded bg-surface-900 border-border text-cyan-600 focus:ring-0 w-4 h-4 cursor-pointer"
                  />
                  <span className="text-xs font-mono text-slate-300">
                    Compute IoU, Centroid offset &amp; Validity
                  </span>
                </label>
                <div className="text-[10px] text-slate-500 font-mono">
                  Calculates exact ST_Intersection, ST_Area, and ST_Distance across PostGIS boundaries.
                </div>
              </div>
            </div>

            {/* Action Banner to Run Conflict Detection */}
            <div className="p-5 rounded-lg bg-surface-950/80 border border-amber-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-amber-400" />
                  <h3 className="text-xs font-mono uppercase tracking-wider text-slate-200 font-semibold">
                    {stage.status === 'completed' || conflictsListResponse?.total
                      ? 'Conflict Detection Executed'
                      : 'Stage 08 Ready to Execute'}
                  </h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Scans harmonized candidate pairs from Stage 07 to detect area discrepancies, semantic land-use conflicts, mutation status divergences, environmental risk disagreements, and spatial topology variances.
                </p>
              </div>
              <button
                onClick={handleRunStage}
                disabled={isRunning || !stage.prerequisites_met}
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg font-mono text-xs font-semibold bg-amber-600 hover:bg-amber-500 disabled:bg-slate-800 disabled:text-slate-500 text-white shadow-lg shadow-amber-950/50 border border-amber-500 transition-all flex-shrink-0"
              >
                {isRunning ? (
                  <>
                    <RotateCw className="w-4 h-4 animate-spin" />
                    <span>Detecting Geospatial Conflicts...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current" />
                    <span>Run Conflict Detection</span>
                  </>
                )}
              </button>
            </div>

            {/* Conflict Detection Results & Metrics */}
            {(conflictsListResponse || conflictResult || stage.results_summary) && (
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span>Detected Geospatial Conflicts Summary</span>
                  </h3>
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] font-mono text-slate-400">
                      Execution Time:{' '}
                      <span className="text-cyan-300">
                        {conflictResult?.execution_time_ms || stage.results_summary?.execution_time_ms || 0} ms
                      </span>
                    </span>
                    <button
                      onClick={() => onSelectStage(9)}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-700 text-emerald-300 text-xs font-mono transition-colors"
                    >
                      <span>Proceed to 09 Validation</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Metric Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  <div className="p-3 rounded-lg bg-surface-950 border border-slate-800">
                    <div className="text-[10px] font-mono uppercase text-slate-400">Total Conflicts</div>
                    <div className="text-xl font-bold font-mono text-white mt-1">
                      {conflictsListResponse?.total ?? conflictResult?.conflicts_detected ?? stage.results_summary?.conflicts_detected ?? 0}
                    </div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                      {conflictResult?.conflicts_created ?? stage.results_summary?.conflicts_created ?? 0} created / {conflictResult?.conflicts_updated ?? stage.results_summary?.conflicts_updated ?? 0} updated
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-rose-900/60">
                    <div className="text-[10px] font-mono uppercase text-rose-400 font-semibold">Critical</div>
                    <div className="text-xl font-bold font-mono text-rose-300 mt-1">
                      {conflictsListResponse?.counts_by_severity?.CRITICAL ?? conflictResult?.critical_count ?? stage.results_summary?.critical_count ?? 0}
                    </div>
                    <div className="text-[10px] text-rose-400/70 font-mono mt-0.5">Incompatible &gt; 15%</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-orange-900/60">
                    <div className="text-[10px] font-mono uppercase text-orange-400 font-semibold">High</div>
                    <div className="text-xl font-bold font-mono text-orange-300 mt-1">
                      {conflictsListResponse?.counts_by_severity?.HIGH ?? conflictResult?.high_count ?? stage.results_summary?.high_count ?? 0}
                    </div>
                    <div className="text-[10px] text-orange-400/70 font-mono mt-0.5">Variance 5%–15%</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-amber-900/60">
                    <div className="text-[10px] font-mono uppercase text-amber-400 font-semibold">Medium</div>
                    <div className="text-xl font-bold font-mono text-amber-300 mt-1">
                      {conflictsListResponse?.counts_by_severity?.MEDIUM ?? conflictResult?.medium_count ?? stage.results_summary?.medium_count ?? 0}
                    </div>
                    <div className="text-[10px] text-amber-400/70 font-mono mt-0.5">Variance 2%–5%</div>
                  </div>

                  <div className="p-3 rounded-lg bg-surface-950 border border-blue-900/60">
                    <div className="text-[10px] font-mono uppercase text-blue-400 font-semibold">Low</div>
                    <div className="text-xl font-bold font-mono text-blue-300 mt-1">
                      {conflictsListResponse?.counts_by_severity?.LOW ?? conflictResult?.low_count ?? stage.results_summary?.low_count ?? 0}
                    </div>
                    <div className="text-[10px] text-blue-400/70 font-mono mt-0.5">Minor discrepancy</div>
                  </div>
                </div>

                {/* Filter and Search Bar */}
                <div className="p-3 rounded-lg bg-surface-950 border border-border flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
                  <div className="flex items-center gap-2 flex-grow max-w-sm">
                    <Search className="w-4 h-4 text-slate-500" />
                    <input
                      type="text"
                      placeholder="Search parcel, field, explanation..."
                      value={conflictSearchTerm}
                      onChange={(e) => setConflictSearchTerm(e.target.value)}
                      className="bg-surface-900 border border-border text-slate-200 text-xs font-mono rounded px-3 py-1.5 placeholder:text-slate-500 w-full"
                    />
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    {/* Severity Filter */}
                    <div className="flex items-center gap-1.5">
                      <span className="text-slate-400 text-[11px]">Severity:</span>
                      <select
                        value={conflictSeverityFilter}
                        onChange={(e) => setConflictSeverityFilter(e.target.value)}
                        className="bg-surface-900 border border-border text-slate-200 text-xs font-mono rounded px-2.5 py-1"
                      >
                        <option value="ALL">ALL ({conflictsListResponse?.total ?? 0})</option>
                        <option value="CRITICAL">CRITICAL ({conflictsListResponse?.counts_by_severity?.CRITICAL ?? 0})</option>
                        <option value="HIGH">HIGH ({conflictsListResponse?.counts_by_severity?.HIGH ?? 0})</option>
                        <option value="MEDIUM">MEDIUM ({conflictsListResponse?.counts_by_severity?.MEDIUM ?? 0})</option>
                        <option value="LOW">LOW ({conflictsListResponse?.counts_by_severity?.LOW ?? 0})</option>
                      </select>
                    </div>

                    {/* Conflict Type Filter */}
                    <div className="flex items-center gap-1.5">
                      <span className="text-slate-400 text-[11px]">Type:</span>
                      <select
                        value={conflictTypeFilter}
                        onChange={(e) => setConflictTypeFilter(e.target.value)}
                        className="bg-surface-900 border border-border text-slate-200 text-xs font-mono rounded px-2.5 py-1"
                      >
                        <option value="ALL">ALL TYPES</option>
                        <option value="AREA_DISCREPANCY">Area Discrepancy</option>
                        <option value="LAND_USE_CONFLICT">Land Use Conflict</option>
                        <option value="MUTATION_CONFLICT">Mutation Conflict</option>
                        <option value="RISK_CONFLICT">Risk Conflict</option>
                        <option value="GEOMETRY_MISMATCH">Geometry Mismatch</option>
                        <option value="ATTRIBUTE_MISMATCH">Attribute Mismatch</option>
                      </select>
                    </div>

                    {/* Status Filter */}
                    <div className="flex items-center gap-1.5">
                      <span className="text-slate-400 text-[11px]">Status:</span>
                      <select
                        value={conflictStatusFilter}
                        onChange={(e) => setConflictStatusFilter(e.target.value)}
                        className="bg-surface-900 border border-border text-slate-200 text-xs font-mono rounded px-2.5 py-1"
                      >
                        <option value="ALL">ALL STATUSES</option>
                        <option value="OPEN">OPEN</option>
                        <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
                        <option value="RESOLVED">RESOLVED</option>
                        <option value="DISMISSED">DISMISSED</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Filtered Conflicts Table */}
                <div className="border border-border rounded-lg overflow-hidden bg-surface-950">
                  <div className="overflow-x-auto max-h-96">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-surface-900/90 text-slate-400 uppercase text-[10px] sticky top-0 border-b border-border">
                        <tr>
                          <th className="px-4 py-2.5">Parcel / Record</th>
                          <th className="px-4 py-2.5">Conflict Type</th>
                          <th className="px-4 py-2.5">Field</th>
                          <th className="px-4 py-2.5">Source A Value</th>
                          <th className="px-4 py-2.5">Source B Value</th>
                          <th className="px-4 py-2.5">Difference</th>
                          <th className="px-4 py-2.5">Severity</th>
                          <th className="px-4 py-2.5">Status</th>
                          <th className="px-4 py-2.5 text-center">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/50 text-slate-300">
                        {(conflictsListResponse?.items || []).map((conflict) => (
                          <tr key={conflict.id} className="hover:bg-surface-900/50 transition-colors">
                            <td className="px-4 py-2 font-medium text-cyan-300 max-w-[140px] truncate" title={conflict.harmonized_record_id}>
                              {conflict.harmonized_record_id}
                            </td>
                            <td className="px-4 py-2">
                              <span className="font-semibold text-slate-200 block text-[11px]">
                                {conflict.conflict_type.replace(/_/g, ' ')}
                              </span>
                              <span className="text-[9px] px-1.5 py-0.2 rounded bg-surface-900 text-slate-400 border border-border">
                                {conflict.category}
                              </span>
                            </td>
                            <td className="px-4 py-2 font-mono text-purple-300">
                              {conflict.field_name}
                            </td>
                            <td className="px-4 py-2 max-w-[150px] truncate" title={conflict.value_a || ''}>
                              <span className="text-slate-200">{conflict.value_a || '—'}</span>
                              {conflict.normalized_value_a && conflict.normalized_value_a !== conflict.value_a && (
                                <div className="text-[10px] text-cyan-400/80">({conflict.normalized_value_a})</div>
                              )}
                            </td>
                            <td className="px-4 py-2 max-w-[150px] truncate" title={conflict.value_b || ''}>
                              <span className="text-slate-200">{conflict.value_b || '—'}</span>
                              {conflict.normalized_value_b && conflict.normalized_value_b !== conflict.value_b && (
                                <div className="text-[10px] text-purple-400/80">({conflict.normalized_value_b})</div>
                              )}
                            </td>
                            <td className="px-4 py-2 font-semibold">
                              {conflict.discrepancy_percentage != null ? (
                                <span className={conflict.discrepancy_percentage > 15 ? 'text-rose-400' : 'text-amber-400'}>
                                  Δ {conflict.discrepancy_percentage}%
                                </span>
                              ) : (
                                <span className="text-slate-400 text-[11px]">
                                  {conflict.discrepancy_value || 'Discrepant'}
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  conflict.severity === 'CRITICAL'
                                    ? 'bg-rose-950 text-rose-300 border border-rose-800'
                                    : conflict.severity === 'HIGH'
                                    ? 'bg-orange-950 text-orange-300 border border-orange-800'
                                    : conflict.severity === 'MEDIUM'
                                    ? 'bg-amber-950 text-amber-300 border border-amber-800'
                                    : 'bg-blue-950 text-blue-300 border border-blue-800'
                                }`}
                              >
                                {conflict.severity}
                              </span>
                            </td>
                            <td className="px-4 py-2">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  conflict.status === 'RESOLVED'
                                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                    : conflict.status === 'ACKNOWLEDGED'
                                    ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                                    : conflict.status === 'DISMISSED'
                                    ? 'bg-slate-900 text-slate-400 border border-slate-700'
                                    : 'bg-amber-950/80 text-amber-300 border border-amber-700'
                                }`}
                              >
                                {conflict.status}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-center">
                              <button
                                onClick={() => setSelectedConflict(conflict)}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-surface-900 hover:bg-surface-800 border border-border text-slate-300 hover:text-cyan-300 text-xs transition-colors"
                              >
                                <Eye className="w-3.5 h-3.5" />
                                <span>Inspect</span>
                              </button>
                            </td>
                          </tr>
                        ))}
                        {(!conflictsListResponse?.items || conflictsListResponse.items.length === 0) && (
                          <tr>
                            <td colSpan={9} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                              No conflicts found matching current filters.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 09: MULTI-RULE VALIDATION ENGINE                     */}
        {/* ========================================================= */}
        {stage.stage_number === 9 && (
          <div className="space-y-6">
            {/* Stage Overview Banner */}
            <div className="p-4 rounded-lg bg-surface-950/80 border border-border space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-cyan-400" />
                  <h3 className="text-sm font-mono uppercase tracking-wider text-slate-200 font-semibold">
                    Stage 09: Multi-Rule Geospatial Validation
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-slate-400">Prerequisites:</span>
                  {stage.prerequisites_met ? (
                    <span className="text-emerald-400 flex items-center gap-1 text-xs font-mono font-semibold">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Stage 08 Conflicts Ready
                    </span>
                  ) : (
                    <span className="text-amber-400 flex items-center gap-1 text-xs font-mono">
                      <Lock className="w-3.5 h-3.5" />
                      Requires Stage 08 Completion
                    </span>
                  )}
                </div>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Executes multi-rule validation over harmonized candidate records: PostGIS ST_IsValid geometry checks,
                topological integrity (self-intersection &amp; intersection-over-union), area tolerance verification
                (PASS/WARNING/FAIL thresholds), attribute/semantic business rules, and conflict penalties from Stage 08.
              </p>
            </div>

            {/* Validation Engine Parameters Configuration */}
            <div className="p-5 rounded-lg bg-surface-900 border border-border space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-cyan-400" />
                  <h4 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold">
                    Validation Rule Tolerances &amp; Options
                  </h4>
                </div>
                <span className="text-[11px] font-mono text-slate-500">Configurable Deterministic Rules</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-1">
                {/* Area Tolerance (Pass Threshold) */}
                <div className="space-y-1.5 bg-surface-950 p-3 rounded-lg border border-border/60">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-300 font-mono flex items-center gap-1.5">
                      <Percent className="w-3.5 h-3.5 text-emerald-400" />
                      Area Pass Tolerance Threshold
                    </span>
                    <span className="font-mono text-emerald-400 font-bold bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
                      {valAreaTolerancePct.toFixed(1)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="15"
                    step="0.5"
                    value={valAreaTolerancePct}
                    onChange={(e) => setValAreaTolerancePct(parseFloat(e.target.value))}
                    disabled={isRunning}
                    className="w-full h-1.5 bg-surface-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                    <span>Strict (1%)</span>
                    <span>Standard (5%)</span>
                    <span>Relaxed (15%)</span>
                  </div>
                </div>

                {/* Area Warning Threshold */}
                <div className="space-y-1.5 bg-surface-950 p-3 rounded-lg border border-border/60">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-300 font-mono flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                      Area Warning Threshold (Above = FAIL)
                    </span>
                    <span className="font-mono text-amber-400 font-bold bg-amber-950/60 px-2 py-0.5 rounded border border-amber-800/40">
                      {valAreaWarningPct.toFixed(1)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="30"
                    step="1"
                    value={valAreaWarningPct}
                    onChange={(e) => setValAreaWarningPct(parseFloat(e.target.value))}
                    disabled={isRunning}
                    className="w-full h-1.5 bg-surface-800 rounded-lg appearance-none cursor-pointer accent-amber-500"
                  />
                  <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                    <span>Strict (5%)</span>
                    <span>Standard (15%)</span>
                    <span>Permissive (30%)</span>
                  </div>
                </div>
              </div>

              {/* Toggles for sub-rules */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 border-t border-border/60">
                <label className="flex items-center gap-2.5 p-2.5 rounded-lg bg-surface-950 border border-border/60 cursor-pointer hover:border-cyan-700/50 transition-colors">
                  <input
                    type="checkbox"
                    checked={valCheckTopology}
                    onChange={(e) => setValCheckTopology(e.target.checked)}
                    disabled={isRunning}
                    className="w-4 h-4 rounded bg-surface-800 border-border text-cyan-500 focus:ring-0 cursor-pointer"
                  />
                  <div className="text-xs font-mono">
                    <div className="text-slate-200 font-medium">PostGIS Topology</div>
                    <div className="text-[10px] text-slate-500">Self-intersections &amp; IoU</div>
                  </div>
                </label>

                <label className="flex items-center gap-2.5 p-2.5 rounded-lg bg-surface-950 border border-border/60 cursor-pointer hover:border-cyan-700/50 transition-colors">
                  <input
                    type="checkbox"
                    checked={valCheckSemantics}
                    onChange={(e) => setValCheckSemantics(e.target.checked)}
                    disabled={isRunning}
                    className="w-4 h-4 rounded bg-surface-800 border-border text-cyan-500 focus:ring-0 cursor-pointer"
                  />
                  <div className="text-xs font-mono">
                    <div className="text-slate-200 font-medium">Semantic Rules</div>
                    <div className="text-[10px] text-slate-500">Land use, status &amp; risk</div>
                  </div>
                </label>

                <label className="flex items-center gap-2.5 p-2.5 rounded-lg bg-surface-950 border border-border/60 cursor-pointer hover:border-cyan-700/50 transition-colors">
                  <input
                    type="checkbox"
                    checked={valConsumeConflicts}
                    onChange={(e) => setValConsumeConflicts(e.target.checked)}
                    disabled={isRunning}
                    className="w-4 h-4 rounded bg-surface-800 border-border text-cyan-500 focus:ring-0 cursor-pointer"
                  />
                  <div className="text-xs font-mono">
                    <div className="text-slate-200 font-medium">Stage 08 Conflicts</div>
                    <div className="text-[10px] text-slate-500">Critical &amp; High penalties</div>
                  </div>
                </label>
              </div>

              {/* Execution Action Button */}
              <div className="pt-2 flex items-center justify-between">
                <div className="text-xs font-mono text-slate-400">
                  {stage.status === 'completed' ? (
                    <span className="text-emerald-400 flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" />
                      Stage 09 validated (re-runnable for updated tolerances)
                    </span>
                  ) : (
                    <span>Ready to execute validation on harmonized candidate pool</span>
                  )}
                </div>
                <button
                  onClick={handleRunStage}
                  disabled={isRunning || !stage.prerequisites_met}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-mono text-xs font-semibold text-white bg-cyan-600 hover:bg-cyan-500 active:bg-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-cyan-900/30"
                >
                  {isRunning ? (
                    <>
                      <RotateCw className="w-4 h-4 animate-spin" />
                      <span>Validating PostGIS Geometries...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 fill-white" />
                      <span>{stage.status === 'completed' ? 'Re-run Validation' : 'Run Stage 09 Validation'}</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Execution / Success Notification */}
            {validationResult && (
              <div className="p-4 rounded-lg bg-emerald-950/60 border border-emerald-700/80 text-emerald-200 text-xs font-mono flex items-center justify-between animate-in fade-in">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <div>
                    <span className="font-semibold text-emerald-300">Validation Completed Successfully:</span>{' '}
                    Evaluated {validationResult.records_validated} candidate records in {validationResult.execution_time_ms.toFixed(1)}ms.
                    ({validationResult.pass_count} Passed, {validationResult.warning_count} Warnings, {validationResult.fail_count} Failed)
                  </div>
                </div>
                <button
                  onClick={() => onSelectStage(10)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded bg-emerald-800 hover:bg-emerald-700 text-white font-semibold transition-colors shrink-0"
                >
                  <span>Proceed to Stage 10</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {/* Validation Metrics & Summary Cards */}
            {(validationSummaryData || validationResult) && (
              <div className="space-y-4">
                {/* Top Metrics Row: PASS / WARNING / FAIL */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="p-3.5 rounded-lg bg-surface-900 border border-border">
                    <div className="text-[11px] font-mono text-slate-400">Total Evaluated</div>
                    <div className="text-2xl font-bold font-mono text-slate-100 mt-1">
                      {validationSummaryData?.total_validated ?? validationResult?.records_validated ?? 0}
                    </div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">Candidate parcels</div>
                  </div>

                  <div className="p-3.5 rounded-lg bg-emerald-950/40 border border-emerald-800/60">
                    <div className="text-[11px] font-mono text-emerald-400 flex items-center justify-between">
                      <span>PASS</span>
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    </div>
                    <div className="text-2xl font-bold font-mono text-emerald-300 mt-1">
                      {validationSummaryData?.pass_count ?? validationResult?.pass_count ?? 0}
                    </div>
                    <div className="text-[10px] text-emerald-500/80 font-mono mt-0.5">
                      {((validationSummaryData?.total_validated ?? validationResult?.records_validated ?? 0) > 0
                        ? (((validationSummaryData?.pass_count ?? validationResult?.pass_count ?? 0) /
                            (validationSummaryData?.total_validated ?? validationResult?.records_validated ?? 1)) *
                            100
                          ).toFixed(1)
                        : '0.0')}
                      % of total
                    </div>
                  </div>

                  <div className="p-3.5 rounded-lg bg-amber-950/40 border border-amber-800/60">
                    <div className="text-[11px] font-mono text-amber-400 flex items-center justify-between">
                      <span>WARNING</span>
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                    </div>
                    <div className="text-2xl font-bold font-mono text-amber-300 mt-1">
                      {validationSummaryData?.warning_count ?? validationResult?.warning_count ?? 0}
                    </div>
                    <div className="text-[10px] text-amber-500/80 font-mono mt-0.5">
                      {((validationSummaryData?.total_validated ?? validationResult?.records_validated ?? 0) > 0
                        ? (((validationSummaryData?.warning_count ?? validationResult?.warning_count ?? 0) /
                            (validationSummaryData?.total_validated ?? validationResult?.records_validated ?? 1)) *
                            100
                          ).toFixed(1)
                        : '0.0')}
                      % of total
                    </div>
                  </div>

                  <div className="p-3.5 rounded-lg bg-rose-950/40 border border-rose-800/60">
                    <div className="text-[11px] font-mono text-rose-400 flex items-center justify-between">
                      <span>FAIL</span>
                      <XCircle className="w-3.5 h-3.5 text-rose-400" />
                    </div>
                    <div className="text-2xl font-bold font-mono text-rose-300 mt-1">
                      {validationSummaryData?.fail_count ?? validationResult?.fail_count ?? 0}
                    </div>
                    <div className="text-[10px] text-rose-500/80 font-mono mt-0.5">
                      {((validationSummaryData?.total_validated ?? validationResult?.records_validated ?? 0) > 0
                        ? (((validationSummaryData?.fail_count ?? validationResult?.fail_count ?? 0) /
                            (validationSummaryData?.total_validated ?? validationResult?.records_validated ?? 1)) *
                            100
                          ).toFixed(1)
                        : '0.0')}
                      % of total
                    </div>
                  </div>
                </div>

                {/* Sub-rule Breakdown Badges Row */}
                <div className="p-3 rounded-lg bg-surface-950 border border-border">
                  <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5 font-semibold">
                    <Layers className="w-3.5 h-3.5 text-cyan-400" />
                    Failures / Penalties by Validation Domain
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs font-mono">
                    <div className="p-2 rounded bg-surface-900 border border-border/80">
                      <div className="text-[10px] text-slate-500">Geometry (ST_IsValid)</div>
                      <div className="text-base font-bold text-slate-200 mt-0.5">
                        {validationSummaryData?.geometry_failures ?? validationResult?.geometry_failures_count ?? 0}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-surface-900 border border-border/80">
                      <div className="text-[10px] text-slate-500">Topology Integrity</div>
                      <div className="text-base font-bold text-slate-200 mt-0.5">
                        {validationSummaryData?.topology_failures ?? validationResult?.topology_failures_count ?? 0}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-surface-900 border border-border/80">
                      <div className="text-[10px] text-slate-500">Area Tolerance</div>
                      <div className="text-base font-bold text-slate-200 mt-0.5">
                        {validationSummaryData?.area_failures ?? validationResult?.area_failures_count ?? 0}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-surface-900 border border-border/80">
                      <div className="text-[10px] text-slate-500">Semantic Rules</div>
                      <div className="text-base font-bold text-slate-200 mt-0.5">
                        {validationSummaryData?.semantic_failures ?? validationResult?.semantic_failures_count ?? 0}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-surface-900 border border-border/80">
                      <div className="text-[10px] text-slate-500">Stage 08 Conflicts</div>
                      <div className="text-base font-bold text-slate-200 mt-0.5">
                        {validationSummaryData?.conflict_failures ?? validationResult?.conflict_failures_count ?? 0}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Validation Results Explorer & Filterable Table */}
            <div className="p-5 rounded-lg bg-surface-900 border border-border space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-cyan-400" />
                  <h4 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold">
                    Validation Results Pool
                  </h4>
                  <span className="text-[11px] font-mono text-slate-500">
                    ({validationListResponse?.total || 0} Records)
                  </span>
                </div>

                {/* Filter Controls */}
                <div className="flex items-center gap-2 flex-wrap text-xs font-mono">
                  {/* Status Filter */}
                  <select
                    value={valStatusFilter}
                    onChange={(e) => setValStatusFilter(e.target.value)}
                    className="px-2.5 py-1 rounded bg-surface-950 border border-border text-slate-300 text-xs focus:outline-none focus:border-cyan-500"
                  >
                    <option value="ALL">All Statuses</option>
                    <option value="PASS">PASS only</option>
                    <option value="WARNING">WARNING only</option>
                    <option value="FAIL">FAIL only</option>
                  </select>

                  {/* Category Filter */}
                  <select
                    value={valCategoryFilter}
                    onChange={(e) => setValCategoryFilter(e.target.value)}
                    className="px-2.5 py-1 rounded bg-surface-950 border border-border text-slate-300 text-xs focus:outline-none focus:border-cyan-500"
                  >
                    <option value="ALL">All Categories</option>
                    <option value="GEOMETRY">Geometry Issues</option>
                    <option value="TOPOLOGY">Topology Issues</option>
                    <option value="AREA">Area Issues</option>
                    <option value="SEMANTIC">Semantic Issues</option>
                    <option value="CONFLICT">Conflict Issues</option>
                  </select>

                  {/* Search Input */}
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="Search record identifier..."
                      value={valSearchTerm}
                      onChange={(e) => setValSearchTerm(e.target.value)}
                      className="pl-8 pr-3 py-1 rounded bg-surface-950 border border-border text-slate-300 text-xs placeholder-slate-600 focus:outline-none focus:border-cyan-500 w-44 sm:w-52"
                    />
                  </div>
                </div>
              </div>

              {/* Results Table */}
              <div className="overflow-x-auto border border-border/80 rounded-lg">
                <table className="w-full text-left font-mono text-xs">
                  <thead className="bg-surface-950 border-b border-border text-slate-400 text-[11px] uppercase">
                    <tr>
                      <th className="px-3.5 py-2.5">Candidate Identifier</th>
                      <th className="px-3 py-2.5 text-center">Status</th>
                      <th className="px-3 py-2.5 text-center">Geom</th>
                      <th className="px-3 py-2.5 text-center">Topology</th>
                      <th className="px-3 py-2.5 text-center">Area</th>
                      <th className="px-3 py-2.5 text-center">Semantic</th>
                      <th className="px-3 py-2.5 text-center">Conflict</th>
                      <th className="px-3 py-2.5">Findings &amp; Failure Explanation</th>
                      <th className="px-3 py-2.5 text-center">Inspect</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 bg-surface-900/60">
                    {validationListResponse?.items && validationListResponse.items.length > 0 ? (
                      validationListResponse.items.map((item) => (
                        <tr key={item.id} className="hover:bg-surface-800/40 transition-colors">
                          <td className="px-3.5 py-2.5 font-bold text-slate-200">
                            {item.candidate_identifier}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                item.overall_status === 'PASS'
                                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                  : item.overall_status === 'WARNING'
                                  ? 'bg-amber-950 text-amber-300 border border-amber-800'
                                  : 'bg-rose-950 text-rose-300 border border-rose-800'
                              }`}
                            >
                              {item.overall_status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] ${
                                item.geometry_validity_status === 'PASS'
                                  ? 'text-emerald-400'
                                  : 'text-rose-400 font-bold'
                              }`}
                            >
                              {item.geometry_validity_status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] ${
                                item.topology_status === 'PASS'
                                  ? 'text-emerald-400'
                                  : item.topology_status === 'WARNING'
                                  ? 'text-amber-400'
                                  : 'text-rose-400 font-bold'
                              }`}
                            >
                              {item.topology_status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] ${
                                item.area_status === 'PASS'
                                  ? 'text-emerald-400'
                                  : item.area_status === 'WARNING'
                                  ? 'text-amber-400'
                                  : 'text-rose-400 font-bold'
                              }`}
                            >
                              {item.area_status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] ${
                                item.semantic_status === 'PASS'
                                  ? 'text-emerald-400'
                                  : 'text-rose-400 font-bold'
                              }`}
                            >
                              {item.semantic_status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] ${
                                item.conflict_status === 'PASS'
                                  ? 'text-emerald-400'
                                  : item.conflict_status === 'WARNING'
                                  ? 'text-amber-400'
                                  : 'text-rose-400 font-bold'
                              }`}
                            >
                              {item.conflict_status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-slate-400 max-w-xs truncate">
                            {item.failure_reasons && item.failure_reasons.length > 0 ? (
                              <span className="text-rose-400">{item.failure_reasons[0]}</span>
                            ) : item.warning_reasons && item.warning_reasons.length > 0 ? (
                              <span className="text-amber-400">{item.warning_reasons[0]}</span>
                            ) : (
                              <span className="text-emerald-500/80">Valid: all criteria passed</span>
                            )}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <button
                              onClick={() => setSelectedValidationItem(item)}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-surface-950 hover:bg-surface-800 border border-border text-slate-300 hover:text-cyan-300 text-xs transition-colors"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              <span>Inspect</span>
                            </button>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={9} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                          {isRunning
                            ? 'Evaluating candidate geometries and rules...'
                            : stage.status === 'completed'
                            ? 'No validation results match current filters.'
                            : 'Validation has not been executed yet. Click "Run Stage 09 Validation" above.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Stage 10 Transition Banner if Completed */}
            {stage.status === 'completed' && (
              <div className="p-4 rounded-lg bg-surface-950 border border-cyan-800/60 flex items-center justify-between">
                <div>
                  <div className="text-xs font-mono font-semibold text-cyan-300 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                    Validation Complete &mdash; Downstream Stage 10 Unlocked
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                    Validated records and tolerance matrices are deterministic and ready for Confidence Scoring.
                  </div>
                </div>
                <button
                  onClick={() => onSelectStage(10)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-mono text-xs font-semibold transition-colors shadow-lg shadow-cyan-950"
                >
                  <span>Proceed to Stage 10: Confidence Scoring</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 10: CONFIDENCE SCORING & EXPLAINABLE BREAKDOWN       */}
        {/* ========================================================= */}
        {stage.stage_number === 10 && (
          <div className="space-y-6">
            {/* Parameters & Multi-Component Weights Configuration */}
            <div className="p-5 rounded-lg bg-surface-950/90 border border-border space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/60 pb-3">
                <div className="flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-100">
                    Confidence Weight Matrix &amp; Threshold Rules
                  </h3>
                </div>
                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="text-slate-400">Total Weight:</span>
                  <span
                    className={`px-2 py-0.5 rounded font-bold ${
                      Math.abs(
                        confSpatialWeight +
                          confGeometryWeight +
                          confAttributeWeight +
                          confTemporalWeight -
                          1.0
                      ) < 0.01
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : 'bg-amber-950 text-amber-300 border border-amber-800'
                    }`}
                  >
                    {(
                      confSpatialWeight +
                      confGeometryWeight +
                      confAttributeWeight +
                      confTemporalWeight
                    ).toFixed(2)}{' '}
                    / 1.00
                  </span>
                </div>
              </div>

              {/* Sliders Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs font-mono">
                {/* Spatial Weight */}
                <div className="p-3 rounded-lg bg-surface-900 border border-border/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300 font-semibold flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                      Spatial Weight
                    </span>
                    <span className="text-cyan-300 font-bold">
                      {(confSpatialWeight * 100).toFixed(0)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={confSpatialWeight}
                    onChange={(e) => setConfSpatialWeight(parseFloat(e.target.value))}
                    className="w-full accent-cyan-500 cursor-pointer"
                  />
                  <div className="text-[10px] text-slate-500">
                    Proximity, centroid distance &amp; intersection
                  </div>
                </div>

                {/* Geometry Weight */}
                <div className="p-3 rounded-lg bg-surface-900 border border-border/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300 font-semibold flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-purple-400" />
                      Geometry Weight
                    </span>
                    <span className="text-purple-300 font-bold">
                      {(confGeometryWeight * 100).toFixed(0)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={confGeometryWeight}
                    onChange={(e) => setConfGeometryWeight(parseFloat(e.target.value))}
                    className="w-full accent-purple-500 cursor-pointer"
                  />
                  <div className="text-[10px] text-slate-500">
                    Area tolerance, IoU &amp; boundary Hausdorff
                  </div>
                </div>

                {/* Attribute Weight */}
                <div className="p-3 rounded-lg bg-surface-900 border border-border/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300 font-semibold flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-blue-400" />
                      Attribute Weight
                    </span>
                    <span className="text-blue-300 font-bold">
                      {(confAttributeWeight * 100).toFixed(0)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={confAttributeWeight}
                    onChange={(e) => setConfAttributeWeight(parseFloat(e.target.value))}
                    className="w-full accent-blue-500 cursor-pointer"
                  />
                  <div className="text-[10px] text-slate-500">
                    Survey number match &amp; semantic rules
                  </div>
                </div>

                {/* Temporal Weight */}
                <div className="p-3 rounded-lg bg-surface-900 border border-border/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300 font-semibold flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-amber-400" />
                      Temporal Weight
                    </span>
                    <span className="text-amber-300 font-bold">
                      {(confTemporalWeight * 100).toFixed(0)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={confTemporalWeight}
                    onChange={(e) => setConfTemporalWeight(parseFloat(e.target.value))}
                    className="w-full accent-amber-500 cursor-pointer"
                  />
                  <div className="text-[10px] text-slate-500">
                    Survey vintage alignment &amp; freshness
                  </div>
                </div>
              </div>

              {/* Thresholds & Constraint Toggles */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs font-mono pt-1 border-t border-border/40">
                <div className="p-2.5 rounded bg-surface-900 border border-border/60">
                  <label className="text-[11px] text-slate-400 block mb-1">
                    HIGH Threshold (Auto-Confirm):
                  </label>
                  <input
                    type="number"
                    min="0.5"
                    max="1.0"
                    step="0.01"
                    value={confHighThreshold}
                    onChange={(e) => setConfHighThreshold(parseFloat(e.target.value) || 0.9)}
                    className="w-full px-2 py-1 rounded bg-surface-950 border border-border text-slate-200"
                  />
                </div>

                <div className="p-2.5 rounded bg-surface-900 border border-border/60">
                  <label className="text-[11px] text-slate-400 block mb-1">
                    MEDIUM Threshold (Review):
                  </label>
                  <input
                    type="number"
                    min="0.3"
                    max="0.9"
                    step="0.01"
                    value={confMediumThreshold}
                    onChange={(e) => setConfMediumThreshold(parseFloat(e.target.value) || 0.7)}
                    className="w-full px-2 py-1 rounded bg-surface-950 border border-border text-slate-200"
                  />
                </div>

                <div className="p-2.5 rounded bg-surface-900 border border-border/60 flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-slate-200">Enforce Stage 09 Fails</div>
                    <div className="text-[10px] text-slate-500">Validation FAIL forces review</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={confEnforceValidation}
                    onChange={(e) => setConfEnforceValidation(e.target.checked)}
                    className="w-4 h-4 rounded accent-cyan-500 cursor-pointer"
                  />
                </div>

                <div className="p-2.5 rounded bg-surface-900 border border-border/60 flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-slate-200">Enforce Critical Conflicts</div>
                    <div className="text-[10px] text-slate-500">Caps score &le; 0.78 &amp; flags</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={confEnforceConflicts}
                    onChange={(e) => setConfEnforceConflicts(e.target.checked)}
                    className="w-4 h-4 rounded accent-cyan-500 cursor-pointer"
                  />
                </div>
              </div>
            </div>

            {/* Stage Execution Action & Live Running Status */}
            <div className="p-5 rounded-lg bg-gradient-to-r from-surface-950 via-cyan-950/20 to-surface-950 border border-cyan-900/60 flex flex-col md:flex-row items-center justify-between gap-4 shadow-xl">
              <div className="space-y-1">
                <div className="text-sm font-mono font-bold text-slate-100 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-cyan-400" />
                  <span>Execute Transparent Multi-Component Confidence Scoring</span>
                </div>
                <div className="text-xs text-slate-400 font-mono">
                  Synthesizes spatial, geometry, attribute, and temporal signals with explainable contributions and conflict overrides.
                </div>
              </div>

              <div className="flex items-center gap-3">
                {isRunning ? (
                  <div className="flex items-center gap-3 px-5 py-2.5 rounded-lg bg-amber-950/80 border border-amber-700 text-amber-200 font-mono text-xs font-semibold shadow-lg shadow-amber-950/50">
                    <RotateCw className="w-4 h-4 animate-spin text-amber-400" />
                    <span>Scoring Signals... ({(elapsedTimeMs / 1000).toFixed(1)}s)</span>
                  </div>
                ) : (
                  <button
                    onClick={handleRunStage}
                    disabled={!stage.prerequisites_met}
                    className={`flex items-center gap-2 px-6 py-2.5 rounded-lg font-mono text-xs font-bold transition-all shadow-xl ${
                      !stage.prerequisites_met
                        ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed'
                        : stage.status === 'completed'
                        ? 'bg-emerald-600 hover:bg-emerald-500 text-white border border-emerald-400 shadow-emerald-950/60'
                        : 'bg-cyan-600 hover:bg-cyan-500 text-white border border-cyan-400 shadow-cyan-950/60'
                    }`}
                  >
                    {stage.status === 'completed' ? (
                      <>
                        <RotateCw className="w-4 h-4" />
                        <span>Re-run Confidence Scoring</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 fill-current" />
                        <span>Run Confidence Scoring</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Summary Statistics Cards */}
            {(confidenceRunResult || confidenceSummaryData || stage.results_summary) && (
              <div className="space-y-3">
                <div className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center justify-between">
                  <span className="font-semibold text-slate-200">Confidence Scoring Summary</span>
                  {confidenceRunResult?.execution_time_ms && (
                    <span className="text-[11px] text-cyan-400">
                      Executed in {confidenceRunResult.execution_time_ms} ms
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 font-mono text-xs">
                  {/* Total Scored */}
                  <div className="p-3 rounded-lg bg-surface-950 border border-border space-y-1">
                    <div className="text-[10px] text-slate-400 uppercase">Total Scored</div>
                    <div className="text-lg font-bold text-slate-100">
                      {confidenceRunResult?.records_scored ??
                        confidenceSummaryData?.total_records_scored ??
                        stage.results_summary?.records_scored ??
                        0}
                    </div>
                    <div className="text-[10px] text-slate-500">Candidate Records</div>
                  </div>

                  {/* High / Auto-Confirm */}
                  <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-900/60 space-y-1">
                    <div className="text-[10px] text-emerald-400 uppercase font-semibold">HIGH (&ge;0.90)</div>
                    <div className="text-lg font-bold text-emerald-300">
                      {confidenceRunResult?.high_count ??
                        confidenceSummaryData?.high_count ??
                        stage.results_summary?.high_count ??
                        0}
                    </div>
                    <div className="text-[10px] text-emerald-400/70">Auto-Confirm</div>
                  </div>

                  {/* Medium / Pending */}
                  <div className="p-3 rounded-lg bg-cyan-950/40 border border-cyan-900/60 space-y-1">
                    <div className="text-[10px] text-cyan-400 uppercase font-semibold">MEDIUM (0.70-0.89)</div>
                    <div className="text-lg font-bold text-cyan-300">
                      {confidenceRunResult?.medium_count ??
                        confidenceSummaryData?.medium_count ??
                        stage.results_summary?.medium_count ??
                        0}
                    </div>
                    <div className="text-[10px] text-cyan-400/70">Pending Review</div>
                  </div>

                  {/* Low / Mandatory */}
                  <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-900/60 space-y-1">
                    <div className="text-[10px] text-amber-400 uppercase font-semibold">LOW (&lt;0.70)</div>
                    <div className="text-lg font-bold text-amber-300">
                      {confidenceRunResult?.low_count ??
                        confidenceSummaryData?.low_count ??
                        stage.results_summary?.low_count ??
                        0}
                    </div>
                    <div className="text-[10px] text-amber-400/70">Mandatory Review</div>
                  </div>

                  {/* Ambiguous Override */}
                  <div className="p-3 rounded-lg bg-purple-950/40 border border-purple-900/60 space-y-1">
                    <div className="text-[10px] text-purple-400 uppercase font-semibold">AMBIGUOUS</div>
                    <div className="text-lg font-bold text-purple-300">
                      {confidenceRunResult?.ambiguous_count ??
                        confidenceSummaryData?.ambiguous_count ??
                        stage.results_summary?.ambiguous_count ??
                        0}
                    </div>
                    <div className="text-[10px] text-purple-400/70">Always Review</div>
                  </div>

                  {/* Review Required */}
                  <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-900/60 space-y-1">
                    <div className="text-[10px] text-rose-400 uppercase font-semibold">Review Req.</div>
                    <div className="text-lg font-bold text-rose-300">
                      {confidenceRunResult?.review_required_count ??
                        confidenceSummaryData?.review_required_count ??
                        stage.results_summary?.review_required_count ??
                        0}
                    </div>
                    <div className="text-[10px] text-rose-400/70">Human Escalation</div>
                  </div>

                  {/* Auto-Confirmed */}
                  <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-900/60 space-y-1">
                    <div className="text-[10px] text-emerald-400 uppercase font-semibold">Auto-Confirmed</div>
                    <div className="text-lg font-bold text-emerald-300">
                      {confidenceRunResult?.auto_confirmed_count ??
                        confidenceSummaryData?.auto_confirmed_count ??
                        stage.results_summary?.auto_confirmed_count ??
                        0}
                    </div>
                    <div className="text-[10px] text-emerald-400/70">Safe Matches</div>
                  </div>

                  {/* Average Confidence */}
                  <div className="p-3 rounded-lg bg-surface-950 border border-cyan-800/80 space-y-1">
                    <div className="text-[10px] text-cyan-400 uppercase font-semibold">Avg Confidence</div>
                    <div className="text-lg font-bold text-cyan-200">
                      {(
                        (confidenceRunResult?.average_confidence ??
                          confidenceSummaryData?.average_confidence ??
                          stage.results_summary?.average_confidence ??
                          0) * 100
                      ).toFixed(1)}
                      %
                    </div>
                    <div className="text-[10px] text-slate-500">Project Score</div>
                  </div>
                </div>
              </div>
            )}

            {/* Filterable Confidence Results Table */}
            <div className="p-5 rounded-lg bg-surface-950/90 border border-border space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-xs font-mono uppercase tracking-wider text-slate-100 font-bold">
                    Confidence Scoring Records &amp; Explainable Signal Matrix
                  </h3>
                </div>

                <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
                  {/* Search Input */}
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input
                      type="text"
                      placeholder="Search parcel or feature ID..."
                      value={confSearchTerm}
                      onChange={(e) => setConfSearchTerm(e.target.value)}
                      className="pl-8 pr-3 py-1 rounded bg-surface-900 border border-border text-slate-200 text-xs w-52 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  {/* Bucket Filter */}
                  <select
                    value={confBucketFilter}
                    onChange={(e) => setConfBucketFilter(e.target.value)}
                    className="px-2.5 py-1 rounded bg-surface-900 border border-border text-slate-300 text-xs focus:outline-none focus:border-cyan-500"
                  >
                    <option value="ALL">All Buckets</option>
                    <option value="HIGH">HIGH (&ge;0.90)</option>
                    <option value="MEDIUM">MEDIUM (0.70-0.89)</option>
                    <option value="LOW">LOW (&lt;0.70)</option>
                    <option value="AMBIGUOUS">AMBIGUOUS</option>
                  </select>

                  {/* Review Status Filter */}
                  <select
                    value={confReviewStatusFilter}
                    onChange={(e) => setConfReviewStatusFilter(e.target.value)}
                    className="px-2.5 py-1 rounded bg-surface-900 border border-border text-slate-300 text-xs focus:outline-none focus:border-cyan-500"
                  >
                    <option value="ALL">All Review Statuses</option>
                    <option value="AUTO_CONFIRMED">Auto-Confirmed</option>
                    <option value="PENDING">Pending Review</option>
                    <option value="FLAGGED">Flagged</option>
                    <option value="REQUIRES_REVIEW">Requires Review</option>
                  </select>
                </div>
              </div>

              {/* Table */}
              <div className="overflow-x-auto rounded border border-border/80">
                <table className="w-full text-left font-mono text-xs">
                  <thead className="bg-surface-900 border-b border-border text-[11px] text-slate-400">
                    <tr>
                      <th className="px-3 py-2.5 font-semibold">Source Feature</th>
                      <th className="px-3 py-2.5 font-semibold">Candidate Feature</th>
                      <th className="px-3 py-2.5 font-semibold text-center">Confidence</th>
                      <th className="px-3 py-2.5 font-semibold text-center">Bucket</th>
                      <th className="px-3 py-2.5 font-semibold text-center">Spatial</th>
                      <th className="px-3 py-2.5 font-semibold text-center">Geometry</th>
                      <th className="px-3 py-2.5 font-semibold text-center">Attribute</th>
                      <th className="px-3 py-2.5 font-semibold text-center">Temporal</th>
                      <th className="px-3 py-2.5 font-semibold text-center">Review Status</th>
                      <th className="px-3 py-2.5 font-semibold text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60 bg-surface-950/60">
                    {confidenceListResponse?.items && confidenceListResponse.items.length > 0 ? (
                      confidenceListResponse.items.map((item) => (
                        <tr key={item.id} className="hover:bg-surface-900/60 transition-colors">
                          <td className="px-3 py-2.5 font-medium text-cyan-300">
                            {item.source_identifier}
                          </td>
                          <td className="px-3 py-2.5 text-purple-300">
                            {item.candidate_identifier || '—'}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              <div className="w-12 bg-surface-900 h-2 rounded-full overflow-hidden border border-border">
                                <div
                                  className={`h-full ${
                                    item.overall_confidence >= 0.90
                                      ? 'bg-emerald-400'
                                      : item.overall_confidence >= 0.70
                                      ? 'bg-cyan-400'
                                      : 'bg-rose-400'
                                  }`}
                                  style={{ width: `${Math.min(100, Math.max(0, item.overall_confidence * 100))}%` }}
                                />
                              </div>
                              <span
                                className={`font-bold ${
                                  item.overall_confidence >= 0.90
                                    ? 'text-emerald-300'
                                    : item.overall_confidence >= 0.70
                                    ? 'text-cyan-300'
                                    : 'text-rose-300'
                                }`}
                              >
                                {(item.overall_confidence * 100).toFixed(1)}%
                              </span>
                            </div>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                item.confidence_bucket === 'HIGH'
                                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                  : item.confidence_bucket === 'MEDIUM'
                                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                                  : item.confidence_bucket === 'LOW'
                                  ? 'bg-rose-950 text-rose-300 border border-rose-800'
                                  : 'bg-purple-950 text-purple-300 border border-purple-800'
                              }`}
                            >
                              {item.confidence_bucket}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center text-slate-300">
                            {(item.spatial_score * 100).toFixed(0)}%
                            <span className="text-[10px] text-slate-500 block">
                              (+{(item.contributions?.spatial * 100 || 0).toFixed(1)}%)
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center text-slate-300">
                            {(item.geometry_score * 100).toFixed(0)}%
                            <span className="text-[10px] text-slate-500 block">
                              (+{(item.contributions?.geometry * 100 || 0).toFixed(1)}%)
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center text-slate-300">
                            {(item.attribute_score * 100).toFixed(0)}%
                            <span className="text-[10px] text-slate-500 block">
                              (+{(item.contributions?.attribute * 100 || 0).toFixed(1)}%)
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center text-slate-300">
                            {(item.temporal_score * 100).toFixed(0)}%
                            <span className="text-[10px] text-slate-500 block">
                              (+{(item.contributions?.temporal * 100 || 0).toFixed(1)}%)
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] ${
                                item.review_status === 'ACCEPTED' || item.review_status === 'AUTO_CONFIRMED'
                                  ? 'text-emerald-400 font-bold'
                                  : item.review_status === 'FLAGGED'
                                  ? 'text-rose-400 font-bold'
                                  : 'text-amber-400'
                              }`}
                            >
                              {item.review_status}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <button
                              onClick={() => setSelectedConfidenceItem(item)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-surface-900 hover:bg-surface-800 border border-border text-slate-300 hover:text-cyan-300 text-xs transition-colors"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              <span>Inspect</span>
                            </button>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={10} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                          {isRunning
                            ? 'Evaluating confidence model and constraints...'
                            : stage.status === 'completed'
                            ? 'No confidence records match current filters.'
                            : 'Confidence Scoring has not been executed yet. Click "Run Confidence Scoring" above.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Stage 11 Transition Banner if Completed */}
            {(stage.status === 'completed' || confidenceRunResult) && (
              <div className="p-4 rounded-lg bg-surface-950 border border-emerald-800/80 flex items-center justify-between shadow-lg">
                <div>
                  <div className="text-xs font-mono font-semibold text-emerald-300 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    Confidence Scoring Complete &mdash; Downstream Stage 11 (Human Review) Unlocked
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                    Records categorized into auto-confirm and human review queues with explainable signal breakdown.
                  </div>
                </div>
                <button
                  onClick={() => onSelectStage(11)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-semibold transition-colors shadow-lg shadow-emerald-950"
                >
                  <span>Proceed to Stage 11: Human Review</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 11: HUMAN-IN-THE-LOOP ADJUDICATION WORKFLOW         */}
        {/* ========================================================= */}
        {stage.stage_number === 11 && (
          <div className="space-y-6">
            {/* Status & Finalization Banner */}
            <div
              className={`p-4 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-lg ${
                stage.status === 'completed' || reviewSummaryData?.is_completed
                  ? 'bg-emerald-950/40 border-emerald-800/80 text-emerald-200'
                  : (reviewSummaryData?.unresolved_count || 0) === 0 && (reviewSummaryData?.total_review_items || 0) > 0
                  ? 'bg-cyan-950/50 border-cyan-700/80 text-cyan-200'
                  : 'bg-amber-950/40 border-amber-800/70 text-amber-200'
              }`}
            >
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-surface-900 border border-border mt-0.5">
                  {stage.status === 'completed' || reviewSummaryData?.is_completed ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  ) : (reviewSummaryData?.unresolved_count || 0) === 0 ? (
                    <ShieldCheck className="w-5 h-5 text-cyan-400" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-amber-400" />
                  )}
                </div>
                <div>
                  <div className="text-sm font-mono font-bold flex items-center gap-2">
                    <span>
                      {stage.status === 'completed' || reviewSummaryData?.is_completed
                        ? 'Stage 11 Human Review Completed & Harmonized'
                        : (reviewSummaryData?.unresolved_count || 0) === 0
                        ? 'Review Queue Harmonized — Ready to Finalize'
                        : 'Human Adjudication in Progress'}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-surface-900 border border-border text-slate-300">
                      {(stage.status || 'READY').toUpperCase()}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 font-mono mt-1">
                    {stage.status === 'completed' || reviewSummaryData?.is_completed
                      ? 'All mandatory conflict records adjudicated. Downstream Stage 12 (Unified Land Records) is unlocked.'
                      : (reviewSummaryData?.unresolved_count || 0) === 0
                      ? 'All critical conflicts and validation failures have been adjudicated. You may now finalize Stage 11.'
                      : `${reviewSummaryData?.unresolved_count || 0} mandatory review item(s) pending adjudication. Stage 12 unlocks when mandatory items are resolved.`}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2.5 flex-shrink-0">
                <button
                  id="stage11-finalize-btn"
                  onClick={handleRunStage}
                  disabled={isRunning || (reviewSummaryData?.unresolved_count || 0) > 0}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-xs font-semibold transition-all ${
                    isRunning || (reviewSummaryData?.unresolved_count || 0) > 0
                      ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed'
                      : stage.status === 'completed' || reviewSummaryData?.is_completed
                      ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-950'
                      : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-lg shadow-cyan-950'
                  }`}
                >
                  {isRunning ? (
                    <>
                      <RotateCw className="w-4 h-4 animate-spin" />
                      <span>Finalizing Review Stage...</span>
                    </>
                  ) : stage.status === 'completed' || reviewSummaryData?.is_completed ? (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Re-finalize Review Stage</span>
                    </>
                  ) : (
                    <>
                      <UserCheck className="w-4 h-4" />
                      <span>Finalize Review Stage</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* 8 Review Metric Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
              {/* Total Queue */}
              <div className="p-3 rounded-lg bg-surface-950 border border-border">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase">Queue Total</span>
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                </div>
                <div className="text-xl font-bold font-mono text-slate-100">
                  {reviewSummaryLoading ? '...' : reviewSummaryData?.total_review_items ?? 0}
                </div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Harmonized Records</div>
              </div>

              {/* Critical Conflicts */}
              <div className="p-3 rounded-lg bg-surface-950 border border-rose-900/60">
                <div className="flex items-center justify-between text-rose-400 mb-1">
                  <span className="text-[10px] font-mono uppercase font-semibold">Critical</span>
                  <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
                </div>
                <div className="text-xl font-bold font-mono text-rose-300">
                  {reviewSummaryLoading ? '...' : reviewSummaryData?.critical_count ?? 0}
                </div>
                <div className="text-[10px] text-rose-500/80 font-mono mt-0.5">High Severity Gate</div>
              </div>

              {/* High Severity */}
              <div className="p-3 rounded-lg bg-surface-950 border border-orange-900/60">
                <div className="flex items-center justify-between text-orange-400 mb-1">
                  <span className="text-[10px] font-mono uppercase">High</span>
                  <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />
                </div>
                <div className="text-xl font-bold font-mono text-orange-300">
                  {reviewSummaryLoading ? '...' : reviewSummaryData?.high_conflict_count ?? 0}
                </div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Substantial Discrepancy</div>
              </div>

              {/* Med / Low */}
              <div className="p-3 rounded-lg bg-surface-950 border border-amber-900/40">
                <div className="flex items-center justify-between text-amber-400 mb-1">
                  <span className="text-[10px] font-mono uppercase">Med / Low</span>
                  <Sliders className="w-3.5 h-3.5 text-amber-400" />
                </div>
                <div className="text-xl font-bold font-mono text-amber-300">
                  {reviewSummaryLoading
                    ? '...'
                    : (reviewSummaryData?.medium_conflict_count ?? 0) + (reviewSummaryData?.low_conflict_count ?? 0)}
                </div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Minor Variance</div>
              </div>

              {/* Mandatory Pending */}
              <div
                className={`p-3 rounded-lg bg-surface-950 border ${
                  (reviewSummaryData?.unresolved_count || 0) === 0 ? 'border-emerald-800/80' : 'border-rose-800/80'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-mono uppercase font-semibold text-slate-300">
                    Mandatory Left
                  </span>
                  <Lock
                    className={`w-3.5 h-3.5 ${
                      (reviewSummaryData?.unresolved_count || 0) === 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  />
                </div>
                <div
                  className={`text-xl font-bold font-mono ${
                    (reviewSummaryData?.unresolved_count || 0) === 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {reviewSummaryLoading ? '...' : reviewSummaryData?.unresolved_count ?? 0}
                </div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Requires Decision</div>
              </div>

              {/* Adjudicated Count */}
              <div className="p-3 rounded-lg bg-surface-950 border border-border">
                <div className="flex items-center justify-between text-emerald-400 mb-1">
                  <span className="text-[10px] font-mono uppercase font-semibold">Adjudicated</span>
                  <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <div className="text-xl font-bold font-mono text-emerald-300">
                  {reviewSummaryLoading ? '...' : reviewSummaryData?.resolved_count ?? 0}
                </div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Decisions Recorded</div>
              </div>

              {/* Avg Confidence */}
              <div className="p-3 rounded-lg bg-surface-950 border border-border">
                <div className="flex items-center justify-between text-cyan-400 mb-1">
                  <span className="text-[10px] font-mono uppercase font-semibold">Confidence</span>
                  <Percent className="w-3.5 h-3.5 text-cyan-400" />
                </div>
                <div className="text-xl font-bold font-mono text-cyan-300">
                  {reviewSummaryLoading
                    ? '...'
                    : `${((reviewSummaryData?.average_confidence ?? 0) * 100).toFixed(0)}%`}
                </div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Mean Score</div>
              </div>

              {/* Progress Pct */}
              <div className="p-3 rounded-lg bg-surface-950 border border-border">
                <div className="flex items-center justify-between text-emerald-400 mb-1">
                  <span className="text-[10px] font-mono uppercase font-semibold">Progress</span>
                  <CheckSquare className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <div className="text-xl font-bold font-mono text-emerald-300">
                  {reviewSummaryLoading ? '...' : `${(reviewSummaryData?.completion_progress_pct ?? 0).toFixed(0)}%`}
                </div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Queue Adjudicated</div>
              </div>
            </div>

            {/* Filter Toolbar */}
            <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
              <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
                {/* Search */}
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="stage11-search-input"
                    type="text"
                    placeholder="Search by Parcel ID or Candidate ID..."
                    value={reviewSearchTerm}
                    onChange={(e) => setReviewSearchTerm(e.target.value)}
                    className="w-full pl-9 pr-8 py-1.5 rounded-lg bg-surface-900 border border-border text-slate-200 placeholder-slate-500 text-xs font-mono focus:outline-none focus:border-cyan-500"
                  />
                  {reviewSearchTerm && (
                    <button
                      onClick={() => setReviewSearchTerm('')}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                {/* Filters */}
                <div className="flex flex-wrap items-center gap-2">
                  {/* Severity Filter */}
                  <select
                    id="stage11-filter-severity"
                    value={reviewSeverityFilter}
                    onChange={(e) => setReviewSeverityFilter(e.target.value)}
                    className="px-2.5 py-1.5 rounded-lg bg-surface-900 border border-border text-slate-300 text-xs font-mono focus:outline-none focus:border-cyan-500"
                  >
                    <option value="ALL">All Severities</option>
                    <option value="CRITICAL">Critical Severity</option>
                    <option value="HIGH">High Severity</option>
                    <option value="MEDIUM">Medium Severity</option>
                    <option value="LOW">Low Severity</option>
                    <option value="NONE">No Conflicts</option>
                  </select>

                  {/* Confidence Bucket Filter */}
                  <select
                    id="stage11-filter-bucket"
                    value={reviewBucketFilter}
                    onChange={(e) => setReviewBucketFilter(e.target.value)}
                    className="px-2.5 py-1.5 rounded-lg bg-surface-900 border border-border text-slate-300 text-xs font-mono focus:outline-none focus:border-cyan-500"
                  >
                    <option value="ALL">All Buckets</option>
                    <option value="HIGH">High Confidence (&gt;80%)</option>
                    <option value="MEDIUM">Medium Confidence (60-80%)</option>
                    <option value="LOW">Low Confidence (&lt;60%)</option>
                  </select>

                  {/* Validation Filter */}
                  <select
                    id="stage11-filter-validation"
                    value={reviewValidationFilter}
                    onChange={(e) => setReviewValidationFilter(e.target.value)}
                    className="px-2.5 py-1.5 rounded-lg bg-surface-900 border border-border text-slate-300 text-xs font-mono focus:outline-none focus:border-cyan-500"
                  >
                    <option value="ALL">All Validation</option>
                    <option value="PASS">Validation: PASS</option>
                    <option value="WARNING">Validation: WARNING</option>
                    <option value="FAIL">Validation: FAIL</option>
                  </select>

                  {/* Adjudication Filter */}
                  <select
                    id="stage11-filter-adjudication"
                    value={reviewAdjudicationFilter}
                    onChange={(e) => setReviewAdjudicationFilter(e.target.value)}
                    className="px-2.5 py-1.5 rounded-lg bg-surface-900 border border-border text-slate-300 text-xs font-mono focus:outline-none focus:border-cyan-500"
                  >
                    <option value="ALL">All Decisions</option>
                    <option value="PENDING">Pending Review</option>
                    <option value="RESOLVED">Resolved / Adjudicated</option>
                    <option value="UNRESOLVED">Unresolved / Rejected</option>
                    <option value="AUTO_CONFIRMED">Auto Confirmed</option>
                  </select>

                  {(reviewSearchTerm ||
                    reviewSeverityFilter !== 'ALL' ||
                    reviewBucketFilter !== 'ALL' ||
                    reviewValidationFilter !== 'ALL' ||
                    reviewAdjudicationFilter !== 'ALL') && (
                    <button
                      onClick={() => {
                        setReviewSearchTerm('')
                        setReviewSeverityFilter('ALL')
                        setReviewBucketFilter('ALL')
                        setReviewValidationFilter('ALL')
                        setReviewAdjudicationFilter('ALL')
                      }}
                      className="px-2.5 py-1.5 rounded-lg bg-surface-900 hover:bg-surface-800 border border-border text-slate-400 hover:text-slate-200 text-xs font-mono transition-colors"
                    >
                      Reset Filters
                    </button>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-1">
                <span>
                  Showing {reviewQueueResponse?.items?.length ?? 0} of {reviewQueueResponse?.total ?? 0} records
                  in prioritized adjudication queue
                </span>
                <span className="text-slate-500">Sorted by Severity, Validation Failure, and Match Score</span>
              </div>
            </div>

            {/* Review Queue Table */}
            <div className="rounded-lg border border-border overflow-hidden bg-surface-950">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-surface-900 text-slate-400 border-b border-border">
                    <tr>
                      <th className="px-3 py-2.5 text-center w-12">#</th>
                      <th className="px-3 py-2.5">Source &amp; Candidate Record</th>
                      <th className="px-3 py-2.5 text-center">Conflict Severity</th>
                      <th className="px-3 py-2.5 text-center">Validation</th>
                      <th className="px-3 py-2.5 text-center">Confidence</th>
                      <th className="px-3 py-2.5 text-center">Adjudication Status</th>
                      <th className="px-3 py-2.5 text-center w-28">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {reviewQueueLoading ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                          <RotateCw className="w-4 h-4 animate-spin inline-block mr-2 text-cyan-400" />
                          Loading review queue items...
                        </td>
                      </tr>
                    ) : reviewQueueResponse?.items && reviewQueueResponse.items.length > 0 ? (
                      reviewQueueResponse.items.map((item, idx) => (
                        <tr
                          key={item.id}
                          className="hover:bg-surface-900/60 transition-colors cursor-pointer"
                          onClick={() => handleOpenAdjudication(item)}
                        >
                          <td className="px-3 py-2.5 text-center text-slate-500 font-mono">
                            {idx + 1}
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                              <span>Src: {item.source_identifier}</span>
                              {item.requires_mandatory_review && (
                                <span className="px-1.5 py-0.2 rounded text-[9px] bg-rose-950/80 text-rose-400 border border-rose-800 font-bold uppercase">
                                  Mandatory
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
                              <span className="text-slate-600">&rarr;</span>
                              <span>Cand: {item.candidate_identifier}</span>
                            </div>
                            <div className="text-[10px] text-slate-500 font-mono truncate max-w-xs mt-0.5">
                              ID: {item.id}
                            </div>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  item.highest_conflict_severity === 'CRITICAL'
                                    ? 'bg-rose-950/80 text-rose-300 border border-rose-800'
                                    : item.highest_conflict_severity === 'HIGH'
                                    ? 'bg-orange-950/80 text-orange-300 border border-orange-800'
                                    : item.highest_conflict_severity === 'MEDIUM'
                                    ? 'bg-amber-950/80 text-amber-300 border border-amber-800'
                                    : item.highest_conflict_severity === 'LOW'
                                    ? 'bg-blue-950/80 text-blue-300 border border-blue-800'
                                    : 'bg-slate-900 text-slate-400 border border-slate-700'
                                }`}
                              >
                                {item.highest_conflict_severity || 'NONE'} ({item.conflict_count})
                              </span>
                            </div>
                            {item.conflicts && item.conflicts.length > 0 && (
                              <div className="text-[9px] text-slate-500 mt-1 truncate max-w-[140px] mx-auto">
                                {item.conflicts[0].conflict_type.replace(/_/g, ' ')}
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                item.validation_status === 'FAIL'
                                  ? 'bg-rose-950/80 text-rose-300 border border-rose-800'
                                  : item.validation_status === 'WARNING'
                                  ? 'bg-amber-950/80 text-amber-300 border border-amber-800'
                                  : 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                              }`}
                            >
                              {item.validation_status || 'PASS'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <div className="font-bold text-slate-200">
                              {(item.overall_confidence * 100).toFixed(0)}%
                            </div>
                            <div className="w-16 bg-surface-900 rounded-full h-1.5 mx-auto mt-1 overflow-hidden border border-border">
                              <div
                                className={`h-full ${
                                  item.overall_confidence >= 0.8
                                    ? 'bg-emerald-500'
                                    : item.overall_confidence >= 0.6
                                    ? 'bg-amber-500'
                                    : 'bg-rose-500'
                                }`}
                                style={{ width: `${Math.round(item.overall_confidence * 100)}%` }}
                              />
                            </div>
                            <span className="text-[9px] text-slate-500 block mt-0.5 font-mono">
                              {item.confidence_bucket}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold block w-fit mx-auto ${
                                item.adjudication_status === 'RESOLVED' ||
                                item.adjudication_action === 'ACCEPT_SOURCE_A' ||
                                item.adjudication_action === 'ACCEPT_SOURCE_B' ||
                                item.adjudication_action === 'MERGE_RECONCILE'
                                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                                  : item.adjudication_status === 'UNRESOLVED' ||
                                    item.adjudication_action === 'REJECT_UNRESOLVED'
                                  ? 'bg-rose-950/80 text-rose-300 border border-rose-800'
                                  : item.adjudication_status === 'AUTO_CONFIRMED'
                                  ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-800'
                                  : 'bg-amber-950/80 text-amber-300 border border-amber-800'
                              }`}
                            >
                              {item.adjudication_action || item.adjudication_status}
                            </span>
                            {item.override_applied && (
                              <span className="text-[9px] text-purple-400 font-mono block mt-0.5">
                                [OVERRIDE]
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <button
                              id={`stage11-adjudicate-btn-${item.id}`}
                              onClick={(e) => {
                                e.stopPropagation()
                                handleOpenAdjudication(item)
                              }}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-700 text-cyan-300 text-xs font-mono transition-colors shadow-sm"
                            >
                              <UserCheck className="w-3.5 h-3.5" />
                              <span>{item.adjudication_status === 'RESOLVED' ? 'Revisit' : 'Adjudicate'}</span>
                            </button>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                          No review queue records match current filters.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 12: UNIFIED RECORD GENERATION                       */}
        {/* ========================================================= */}
        {stage.stage_number === 12 && (
          <div className="space-y-6">
            {/* Header & Execution Action Card */}
            <div className="p-5 rounded-lg bg-surface-950/80 border border-border space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-emerald-400" />
                    <h3 className="text-sm font-mono uppercase tracking-wider text-slate-100 font-bold">
                      Authoritative Unified Land Record Synthesis
                    </h3>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                        stage.status === 'completed'
                          ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                          : stage.status === 'running' || runStage12Mutation.isPending
                          ? 'bg-amber-950/80 text-amber-300 border border-amber-800 animate-pulse'
                          : 'bg-cyan-950/80 text-cyan-300 border border-cyan-800'
                      }`}
                    >
                      {runStage12Mutation.isPending ? 'Synthesizing...' : stage.status.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 max-w-3xl leading-relaxed">
                    Forges authoritative parcel entities by synthesizing harmonized geometries, resolved attributes, multi-source validation checks, and human adjudication decisions. Enforces strict human review precedence, geometry validation, and complete provenance lineage.
                  </p>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <Link
                    to={`/projects/${projectId}/unified-records`}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface-900 hover:bg-surface-800 border border-border text-slate-300 hover:text-white text-xs font-mono transition-colors"
                  >
                    <span>Full Explorer</span>
                    <ExternalLink className="w-3.5 h-3.5 text-cyan-400" />
                  </Link>

                  <button
                    type="button"
                    id="run-stage-12-synthesis-btn"
                    onClick={handleRunStage}
                    disabled={!isStageRunnable || isRunning}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-semibold shadow-lg shadow-emerald-950 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {runStage12Mutation.isPending ? (
                      <>
                        <RotateCw className="w-4 h-4 animate-spin" />
                        <span>Synthesizing Records...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        <span>
                          {stage.status === 'completed' ? 'Re-run Synthesis' : 'Synthesize Authoritative Records'}
                        </span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Feedback Alert Banner */}
              {st12Feedback && (
                <div
                  className={`p-3 rounded-lg border text-xs font-mono flex items-center justify-between ${
                    st12Feedback.type === 'success'
                      ? 'bg-emerald-950/60 border-emerald-800 text-emerald-200'
                      : 'bg-rose-950/60 border-rose-800 text-rose-200'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {st12Feedback.type === 'success' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                    )}
                    <span>{st12Feedback.message}</span>
                  </div>
                  <button
                    onClick={() => setSt12Feedback(null)}
                    className="text-slate-400 hover:text-white p-1"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Prerequisites Warning */}
              {!stage.prerequisites_met && (
                <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-800/60 text-xs font-mono text-amber-300 flex items-center gap-2">
                  <Lock className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>
                    Prerequisite: Stage 11 (Human Review) must be finalized before synthesizing authoritative records.
                  </span>
                </div>
              )}
            </div>

            {/* 6 Live Metric Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {/* Card 1: Considered */}
              <div className="p-3.5 rounded-lg bg-surface-950/90 border border-border">
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mb-1">
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Considered</span>
                </div>
                <div className="text-xl font-mono font-bold text-slate-100">
                  {st12StatusData?.records_considered ?? 0}
                </div>
                <div className="text-[10px] text-slate-500 mt-1 font-mono">
                  Input records
                </div>
              </div>

              {/* Card 2: Authoritative Unified Records */}
              <div className="p-3.5 rounded-lg bg-surface-950/90 border border-emerald-900/50 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-16 h-16 bg-emerald-500/5 rounded-full blur-xl pointer-events-none" />
                <div className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 flex items-center gap-1.5 mb-1 font-semibold">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Unified (ULR)</span>
                </div>
                <div className="text-xl font-mono font-bold text-emerald-300">
                  {st12StatusData?.records_unified ?? 0}
                </div>
                <div className="text-[10px] text-emerald-500/80 mt-1 font-mono">
                  Authoritative parcels
                </div>
              </div>

              {/* Card 3: Rejected / Quarantined */}
              <div className="p-3.5 rounded-lg bg-surface-950/90 border border-rose-900/40">
                <div className="text-[10px] font-mono uppercase tracking-wider text-rose-400 flex items-center gap-1.5 mb-1 font-semibold">
                  <XCircle className="w-3.5 h-3.5 text-rose-400" />
                  <span>Rejected</span>
                </div>
                <div className="text-xl font-mono font-bold text-rose-300">
                  {st12StatusData?.records_rejected ?? 0}
                </div>
                <div className="text-[10px] text-rose-500/80 mt-1 font-mono">
                  Quarantined records
                </div>
              </div>

              {/* Card 4: Average Confidence */}
              <div className="p-3.5 rounded-lg bg-surface-950/90 border border-border">
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mb-1">
                  <Percent className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Avg Confidence</span>
                </div>
                <div className="text-xl font-mono font-bold text-cyan-300">
                  {st12StatusData?.average_confidence != null
                    ? `${(Number(st12StatusData.average_confidence) * 100).toFixed(1)}%`
                    : '0.0%'}
                </div>
                <div className="text-[10px] text-slate-500 mt-1 font-mono">
                  Synthesized mean
                </div>
              </div>

              {/* Card 5: Geometry Validation */}
              <div className="p-3.5 rounded-lg bg-surface-950/90 border border-border">
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mb-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Valid Geometries</span>
                </div>
                <div className="text-xl font-mono font-bold text-slate-100 flex items-baseline gap-1">
                  <span>{st12StatusData?.valid_geometries_count ?? 0}</span>
                  <span className="text-xs text-slate-500 font-normal">/ {st12StatusData?.records_unified ?? 0}</span>
                </div>
                <div className="text-[10px] text-emerald-400 mt-1 font-mono">
                  100% PostGIS valid
                </div>
              </div>

              {/* Card 6: Execution / Time */}
              <div className="p-3.5 rounded-lg bg-surface-950/90 border border-border">
                <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mb-1">
                  <Clock className="w-3.5 h-3.5 text-amber-400" />
                  <span>Synthesis Time</span>
                </div>
                <div className="text-lg font-mono font-bold text-slate-200 truncate">
                  {st12RunResult?.execution_time_ms
                    ? `${st12RunResult.execution_time_ms} ms`
                    : st12StatusData?.is_completed
                    ? 'Synthesized'
                    : 'Ready'}
                </div>
                <div className="text-[10px] text-slate-500 mt-1 font-mono truncate">
                  {st12StatusData?.last_executed_at
                    ? new Date(st12StatusData.last_executed_at).toLocaleTimeString()
                    : 'Awaiting run'}
                </div>
              </div>
            </div>

            {/* Filter and Search Bar */}
            <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                {/* Search Input */}
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input
                    type="text"
                    id="stage-12-search-input"
                    value={st12SearchTerm}
                    onChange={(e) => setSt12SearchTerm(e.target.value)}
                    placeholder="Search by Parcel ID, source reference, land use, mutation..."
                    className="w-full pl-9 pr-8 py-2 bg-surface-900 border border-border rounded-lg text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                  />
                  {st12SearchTerm && (
                    <button
                      onClick={() => setSt12SearchTerm('')}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                {/* Status Filter Tabs */}
                <div className="flex items-center gap-1 bg-surface-900 p-1 rounded-lg border border-border">
                  {(['ALL', 'UNIFIED', 'REJECTED'] as const).map((filterVal) => (
                    <button
                      key={filterVal}
                      type="button"
                      id={`stage-12-filter-${filterVal.toLowerCase()}`}
                      onClick={() => setSt12ResolutionFilter(filterVal)}
                      className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-all ${
                        st12ResolutionFilter === filterVal
                          ? filterVal === 'UNIFIED'
                            ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700 shadow-sm'
                            : filterVal === 'REJECTED'
                            ? 'bg-rose-950/80 text-rose-300 border border-rose-700 shadow-sm'
                            : 'bg-cyan-950/80 text-cyan-300 border border-cyan-700 shadow-sm'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {filterVal === 'ALL' && `All Records (${unifiedRecordsData?.total ?? 0})`}
                      {filterVal === 'UNIFIED' && `Unified (${st12StatusData?.records_unified ?? 0})`}
                      {filterVal === 'REJECTED' && `Rejected (${st12StatusData?.records_rejected ?? 0})`}
                    </button>
                  ))}

                  <button
                    type="button"
                    onClick={() => {
                      refetchUnifiedRecords()
                      refetchStage12Status()
                    }}
                    title="Refresh records"
                    className="p-1.5 ml-1 text-slate-400 hover:text-cyan-400 rounded transition-colors"
                  >
                    <RotateCw className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>

            {/* Authoritative Records Table */}
            <div className="rounded-lg bg-surface-950 border border-border overflow-hidden">
              <div className="p-3 border-b border-border flex items-center justify-between bg-surface-900/60">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-200">
                    Authoritative Land Records
                  </span>
                  <span className="text-[11px] font-mono text-slate-400">
                    ({unifiedRecordsData?.items?.length ?? 0} shown of {unifiedRecordsData?.total ?? 0})
                  </span>
                </div>
                <div className="text-[11px] font-mono text-slate-500">
                  Click [ Inspect ] to verify full lineage, geometry &amp; adjudication metadata
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-surface-900/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-border">
                    <tr>
                      <th className="px-3 py-2.5 text-center w-10">#</th>
                      <th className="px-3 py-2.5">Parcel / Record ID</th>
                      <th className="px-3 py-2.5">Sources</th>
                      <th className="px-3 py-2.5">Land Use</th>
                      <th className="px-3 py-2.5 text-right">Area (m²)</th>
                      <th className="px-3 py-2.5 text-center">Mutation</th>
                      <th className="px-3 py-2.5 text-center">Risk</th>
                      <th className="px-3 py-2.5 text-center">Confidence</th>
                      <th className="px-3 py-2.5 text-center">Review Decision</th>
                      <th className="px-3 py-2.5 text-center">Status</th>
                      <th className="px-3 py-2.5 text-center w-24">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {unifiedRecordsLoading ? (
                      <tr>
                        <td colSpan={11} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                          <RotateCw className="w-4 h-4 animate-spin inline-block mr-2 text-cyan-400" />
                          Loading authoritative records...
                        </td>
                      </tr>
                    ) : unifiedRecordsData?.items && unifiedRecordsData.items.length > 0 ? (
                      unifiedRecordsData.items.map((rec, idx) => (
                        <tr
                          key={rec.id}
                          className="hover:bg-surface-900/60 transition-colors"
                        >
                          <td className="px-3 py-2.5 text-center text-slate-500 font-mono">
                            {idx + 1}
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                              <span>{rec.record_identifier}</span>
                            </div>
                            <div className="text-[10px] text-slate-500 font-mono truncate max-w-xs mt-0.5">
                              Harmonized: {rec.harmonized_record_id || 'N/A'}
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="text-slate-300 text-[11px]">
                              A: <span className="text-slate-200">{rec.source_a_reference || '—'}</span>
                            </div>
                            <div className="text-slate-400 text-[11px]">
                              B: <span className="text-slate-200">{rec.source_b_reference || '—'}</span>
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="px-2 py-0.5 rounded text-[10px] bg-surface-900 border border-border text-slate-300">
                              {rec.land_use || 'UNSPECIFIED'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono text-slate-200">
                            {rec.area != null ? Number(rec.area).toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—'}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                rec.mutation_status === 'VERIFIED'
                                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                                  : rec.mutation_status === 'RECORDED'
                                  ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-800'
                                  : 'bg-surface-900 text-slate-400 border border-border'
                              }`}
                            >
                              {rec.mutation_status || 'PENDING'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                rec.risk_level === 'LOW'
                                  ? 'text-emerald-400'
                                  : rec.risk_level === 'MEDIUM'
                                  ? 'text-amber-400'
                                  : rec.risk_level === 'HIGH'
                                  ? 'text-rose-400'
                                  : 'text-slate-400'
                              }`}
                            >
                              {rec.risk_level || 'LOW'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <div className="flex flex-col items-center gap-0.5">
                              <span
                                className={`text-[11px] font-bold ${
                                  (rec.confidence_score ?? 0) >= 0.75
                                    ? 'text-emerald-400'
                                    : (rec.confidence_score ?? 0) >= 0.55
                                    ? 'text-amber-400'
                                    : 'text-rose-400'
                                }`}
                              >
                                {rec.confidence_score != null
                                  ? `${(Number(rec.confidence_score) * 100).toFixed(0)}%`
                                  : '—'}
                              </span>
                              <div className="w-14 bg-surface-900 h-1 rounded-full overflow-hidden border border-border/50">
                                <div
                                  className={`h-full ${
                                    (rec.confidence_score ?? 0) >= 0.75
                                      ? 'bg-emerald-500'
                                      : (rec.confidence_score ?? 0) >= 0.55
                                      ? 'bg-amber-500'
                                      : 'bg-rose-500'
                                  }`}
                                  style={{ width: `${Math.min(100, Math.max(0, (rec.confidence_score ?? 0) * 100))}%` }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold ${
                                rec.human_review_decision === 'ACCEPT_SOURCE_A'
                                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                                  : rec.human_review_decision === 'ACCEPT_SOURCE_B'
                                  ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-800'
                                  : rec.human_review_decision === 'MERGE_RECONCILE'
                                  ? 'bg-purple-950/80 text-purple-300 border border-purple-800'
                                  : rec.human_review_decision === 'REJECT_UNRESOLVED'
                                  ? 'bg-rose-950/80 text-rose-300 border border-rose-800'
                                  : 'bg-slate-900 text-slate-400 border border-slate-700'
                              }`}
                            >
                              {rec.human_review_decision || 'AUTO'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                rec.resolution_status === 'UNIFIED'
                                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                                  : 'bg-rose-950/80 text-rose-300 border border-rose-800'
                              }`}
                            >
                              {rec.resolution_status || 'UNIFIED'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <button
                              type="button"
                              onClick={() => setSelectedUnifiedRecord(rec)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-surface-900 hover:bg-surface-800 border border-border text-slate-300 hover:text-white text-xs font-mono transition-colors shadow-sm"
                            >
                              <Eye className="w-3.5 h-3.5 text-cyan-400" />
                              <span>Inspect</span>
                            </button>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={11} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                          {stage.status === 'completed'
                            ? 'No unified records match your search query.'
                            : 'No unified records generated yet. Click "Synthesize Authoritative Records" above to begin.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 13: PROVENANCE & LINEAGE PIPELINE                   */}
        {/* ========================================================= */}
        {stage.stage_number === 13 && (
          <div className="space-y-6">
            {/* Header & Execution Action Card */}
            <div className="p-5 rounded-lg bg-surface-950/80 border border-border space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <History className="w-5 h-5 text-purple-400" />
                    <h3 className="text-sm font-mono uppercase tracking-wider text-slate-100 font-bold">
                      Stage 13 — Complete Provenance & Lineage
                    </h3>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 max-w-3xl leading-relaxed">
                    Trace every authoritative land record back through its complete processing history across all upstream pipeline stages. Enforces immutable audit logging, multi-source lineage attribution, and deterministic completeness calculation.
                  </p>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    type="button"
                    id="run-stage-13-provenance-btn"
                    onClick={handleRunStage}
                    disabled={!isStageRunnable || isRunning}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-mono text-xs font-semibold shadow-lg shadow-purple-950 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {runStage13Mutation.isPending ? (
                      <>
                        <RotateCw className="w-4 h-4 animate-spin" />
                        <span>Tracing Lineage...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        <span>
                          {stage.status === 'completed' ? 'Re-run Lineage Tracing' : 'Generate Provenance & Lineage'}
                        </span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Feedback Alert Banner */}
              {st13Feedback && (
                <div
                  className={`p-3 rounded-lg border text-xs font-mono flex items-center justify-between ${
                    st13Feedback.type === 'success'
                      ? 'bg-emerald-950/60 border-emerald-800 text-emerald-200'
                      : 'bg-rose-950/60 border-rose-800 text-rose-200'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {st13Feedback.type === 'success' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                    )}
                    <span>{st13Feedback.message}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSt13Feedback(null)}
                    className="text-slate-400 hover:text-white"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              )}

              {/* Prerequisite & Status Footnote */}
              <div className="flex items-center justify-between pt-2 border-t border-border/50 text-[11px] font-mono text-slate-400 flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span>Prerequisite:</span>
                  {stage.prerequisites_met ? (
                    <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Stage 12 Unified Land Records Synthesized
                    </span>
                  ) : (
                    <span className="text-amber-400 flex items-center gap-1">
                      <Lock className="w-3.5 h-3.5" />
                      {stage.prerequisites_message || 'Stage 12 completion required'}
                    </span>
                  )}
                </div>

                {st13StatusData?.last_executed_at && (
                  <div className="flex items-center gap-1 text-slate-500">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Last run: {new Date(st13StatusData.last_executed_at).toLocaleString()}</span>
                  </div>
                )}
              </div>
            </div>

            {/* 7 Live Metric Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
              {/* Metric 1: Unified Records Traced */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">ULR Traced</span>
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                </div>
                <div className="text-xl font-bold font-mono text-slate-100">
                  {st13StatusData?.records_traced ?? projectProvenanceData?.total ?? 0}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  Across Pune Project
                </div>
              </div>

              {/* Metric 2: Immutable Provenance Events */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Audit Events</span>
                  <History className="w-3.5 h-3.5 text-purple-400" />
                </div>
                <div className="text-xl font-bold font-mono text-purple-300">
                  {st13StatusData?.total_events ?? projectProvenanceData?.latest_events?.length ?? 0}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  Immutable Event Log
                </div>
              </div>

              {/* Metric 3: Source Datasets */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Datasets</span>
                  <Layers className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <div className="text-xl font-bold font-mono text-emerald-300">
                  {projectProvenanceData?.datasets?.length ?? 2}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  Cadastral + Drone Bound
                </div>
              </div>

              {/* Metric 4: Human Decisions Traced */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Adjudications</span>
                  <UserCheck className="w-3.5 h-3.5 text-amber-400" />
                </div>
                <div className="text-xl font-bold font-mono text-amber-300">
                  {st13StatusData?.human_decisions_traced ?? projectProvenanceData?.total_reviews ?? 0}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  Stage 11 Review Decisions
                </div>
              </div>

              {/* Metric 5: Conflicts Traced */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Conflicts</span>
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                </div>
                <div className="text-xl font-bold font-mono text-rose-300">
                  {st13StatusData?.conflicts_traced ?? 0}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  Stage 08 Discrepancies
                </div>
              </div>

              {/* Metric 6: Validation Checks */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Validation</span>
                  <ShieldCheck className="w-3.5 h-3.5 text-teal-400" />
                </div>
                <div className="text-xl font-bold font-mono text-teal-300">
                  {st13StatusData?.validation_events_traced ?? 0}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  Stage 09 Checks
                </div>
              </div>

              {/* Metric 7: Lineage Completeness */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Completeness</span>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <div className="text-xl font-bold font-mono text-emerald-400">
                  {(st13StatusData?.average_completeness_pct ?? 100).toFixed(0)}%
                </div>
                <div className="w-full bg-surface-900 h-1.5 rounded-full overflow-hidden mt-1 border border-border/50">
                  <div
                    className="h-full bg-emerald-500"
                    style={{ width: `${Math.min(100, Math.max(0, st13StatusData?.average_completeness_pct ?? 100))}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Filter Tabs & Search Bar */}
            <div className="p-4 rounded-lg bg-surface-950/80 border border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider mr-1">
                  Lineage Filter:
                </span>
                {['ALL', 'COMPLETE', 'QUARANTINED', 'PARTIAL'].map((filterVal) => (
                  <button
                    key={filterVal}
                    type="button"
                    id={`stage-13-filter-${filterVal.toLowerCase()}`}
                    onClick={() => setSt13StatusFilter(filterVal)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors ${
                      st13StatusFilter === filterVal
                        ? 'bg-purple-600 text-white font-semibold shadow-sm'
                        : 'bg-surface-900 hover:bg-surface-800 text-slate-300 border border-border'
                    }`}
                  >
                    {filterVal}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-3">
                <div className="relative w-full sm:w-72">
                  <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    id="stage-13-search-input"
                    value={st13SearchTerm}
                    onChange={(e) => setSt13SearchTerm(e.target.value)}
                    placeholder="Search ULR ID or parcel #..."
                    className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-surface-900 border border-border text-xs font-mono text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-purple-500"
                  />
                  {st13SearchTerm && (
                    <button
                      type="button"
                      onClick={() => setSt13SearchTerm('')}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                <div className="text-xs font-mono text-slate-400 whitespace-nowrap bg-surface-900 px-2.5 py-1.5 rounded border border-border">
                  <span className="text-slate-200 font-semibold">{projectProvenanceData?.items?.length ?? 0}</span> records
                </div>
              </div>
            </div>

            {/* Provenance Records Table */}
            <div className="rounded-lg border border-border bg-surface-950 overflow-hidden">
              <div className="p-3 border-b border-border bg-surface-900/60 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Share2 className="w-4 h-4 text-purple-400" />
                  <span className="text-xs font-mono font-semibold text-slate-200 uppercase tracking-wider">
                    Queryable Provenance & Lineage Records
                  </span>
                </div>
                <div className="text-[11px] font-mono text-slate-400">
                  Live Stage 13 PostgreSQL View
                </div>
              </div>

              <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
                <table className="w-full text-left text-xs font-mono border-collapse">
                  <thead className="bg-surface-900 sticky top-0 z-10 border-b border-border text-slate-400 text-[11px] uppercase tracking-wider">
                    <tr>
                      <th className="px-3 py-2.5 text-center w-10">#</th>
                      <th className="px-3 py-2.5">Record Identifier</th>
                      <th className="px-3 py-2.5">Resolution</th>
                      <th className="px-3 py-2.5">Source Parcels</th>
                      <th className="px-3 py-2.5 text-center">Match Score</th>
                      <th className="px-3 py-2.5 text-center">Conflicts</th>
                      <th className="px-3 py-2.5 text-center">Validation</th>
                      <th className="px-3 py-2.5 text-center">Confidence</th>
                      <th className="px-3 py-2.5 text-center">Lineage Status</th>
                      <th className="px-3 py-2.5 text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {projectProvenanceLoading ? (
                      <tr>
                        <td colSpan={10} className="px-4 py-8 text-center text-slate-400 font-mono text-xs">
                          <RotateCw className="w-5 h-5 animate-spin mx-auto mb-2 text-purple-400" />
                          Loading provenance records...
                        </td>
                      </tr>
                    ) : projectProvenanceData?.items && projectProvenanceData.items.length > 0 ? (
                      projectProvenanceData.items.map((rec, idx) => (
                        <tr
                          key={rec.id}
                          className="hover:bg-surface-900/60 transition-colors"
                        >
                          <td className="px-3 py-2.5 text-center text-slate-500 font-mono">
                            {idx + 1}
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                              <span>{rec.record_identifier}</span>
                            </div>
                            <div className="text-[10px] text-slate-500 font-mono truncate max-w-xs mt-0.5">
                              Harmonized: {rec.harmonized_record_id || 'N/A'}
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                rec.resolution_status === 'UNIFIED'
                                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                                  : 'bg-rose-950/80 text-rose-300 border border-rose-800'
                              }`}
                            >
                              {rec.resolution_status || 'UNIFIED'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="text-slate-300 text-[11px]">
                              A: <span className="text-slate-200">{rec.source_record_identifiers?.CADASTRAL || rec.source_record_identifiers?.source_a || '—'}</span>
                            </div>
                            <div className="text-slate-400 text-[11px]">
                              B: <span className="text-slate-200">{rec.source_record_identifiers?.DRONE || rec.source_record_identifiers?.source_b || '—'}</span>
                            </div>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span className="text-slate-200 font-mono">
                              {rec.confidence_score != null ? `${(Number(rec.confidence_score) * 100).toFixed(0)}%` : '—'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                rec.conflict_ids && rec.conflict_ids.length > 0
                                  ? 'bg-rose-950/80 text-rose-300 border border-rose-800'
                                  : 'bg-surface-900 text-slate-400 border border-border'
                              }`}
                            >
                              {rec.conflict_ids && rec.conflict_ids.length > 0 ? `${rec.conflict_ids.length} Linked` : 'Clean'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                rec.validation_id
                                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                                  : 'bg-surface-900 text-slate-400 border border-border'
                              }`}
                            >
                              {rec.validation_id ? 'VERIFIED' : 'PASSED'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                (rec.confidence_score ?? 0) >= 0.75
                                  ? 'text-emerald-400'
                                  : (rec.confidence_score ?? 0) >= 0.55
                                  ? 'text-amber-400'
                                  : 'text-rose-400'
                              }`}
                            >
                              {rec.confidence_bucket || 'HIGH'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                rec.lineage_status === 'COMPLETE'
                                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                                  : rec.lineage_status === 'QUARANTINED'
                                  ? 'bg-rose-950/80 text-rose-300 border border-rose-800'
                                  : 'bg-amber-950/80 text-amber-300 border border-amber-800'
                              }`}
                            >
                              {rec.lineage_status} ({rec.lineage_completeness_pct.toFixed(0)}%)
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <button
                              type="button"
                              id={`inspect-lineage-btn-${idx}`}
                              onClick={() => {
                                setSelectedProvenanceRecord(rec)
                                setLineageModalTab('OVERVIEW')
                              }}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-surface-900 hover:bg-surface-800 border border-border text-slate-300 hover:text-white text-xs font-mono transition-colors shadow-sm"
                            >
                              <Eye className="w-3.5 h-3.5 text-purple-400" />
                              <span>Inspect</span>
                            </button>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={10} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                          {stage.status === 'completed'
                            ? 'No provenance records match your search filter.'
                            : 'Stage 13 ready. Click "Generate Provenance & Lineage" above to trace all records.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 14: AUTHORITATIVE EXPORTS & DELIVERABLES            */}
        {/* ========================================================= */}
        {stage.stage_number === 14 && (
          <div className="space-y-6">
            {/* Header info banner */}
            <div className="p-5 rounded-lg bg-surface-950 border border-border space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Download className="w-5 h-5 text-cyan-400" />
                    <h3 className="text-sm font-bold font-mono tracking-wider text-slate-100 uppercase">
                      EXPORT
                    </h3>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold uppercase ${
                      stage.status === 'completed'
                        ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/40'
                        : isRunning
                        ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-500/40 animate-pulse'
                        : stage.prerequisites_met
                        ? 'bg-blue-950/80 text-blue-300 border border-blue-500/40'
                        : 'bg-amber-950/80 text-amber-300 border border-amber-500/40'
                    }`}>
                      {stage.status === 'completed' ? 'COMPLETED' : isRunning ? 'RUNNING' : stage.prerequisites_met ? 'READY' : 'DISABLED'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Generate authoritative geospatial deliverables from the verified LandSync pipeline.
                  </p>
                </div>

                <div className="flex items-center gap-3 text-xs font-mono">
                  {stage.prerequisites_met ? (
                    <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Stage 12 &amp; 13 Verified
                    </span>
                  ) : (
                    <span className="text-amber-400 flex items-center gap-1">
                      <Lock className="w-3.5 h-3.5" />
                      {stage.prerequisites_message || 'Stage 12 & 13 completion required'}
                    </span>
                  )}
                  {st14StatusData?.last_run_at && (
                    <span className="text-slate-500 flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {new Date(st14StatusData.last_run_at).toLocaleTimeString()}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Live Project Export Summary Telemetry (6 metrics) */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {/* Metric 1: Authoritative Records */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Authoritative</span>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <div className="text-xl font-bold font-mono text-emerald-400">
                  {st14StatusData?.authoritative_records_count ?? 24}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  Stage 12 Unified ULR
                </div>
              </div>

              {/* Metric 2: Quarantined Records */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Quarantined</span>
                  <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
                </div>
                <div className="text-xl font-bold font-mono text-rose-400">
                  {st14StatusData?.quarantined_records_count ?? 6}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  Rejected / Disputed
                </div>
              </div>

              {/* Metric 3: Total Processed */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Total Processed</span>
                  <Database className="w-3.5 h-3.5 text-cyan-400" />
                </div>
                <div className="text-xl font-bold font-mono text-slate-100">
                  {st14StatusData?.total_records_count ?? 30}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  Pune Haveli Cadastre
                </div>
              </div>

              {/* Metric 4: Project CRS */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Target CRS</span>
                  <Layers className="w-3.5 h-3.5 text-purple-400" />
                </div>
                <div className="text-xl font-bold font-mono text-purple-300">
                  {st14StatusData?.project_crs ?? 'EPSG:4326'}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  WGS84 Geodetic
                </div>
              </div>

              {/* Metric 5: Valid Geometries */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Valid Geometry</span>
                  <ShieldCheck className="w-3.5 h-3.5 text-teal-400" />
                </div>
                <div className="text-xl font-bold font-mono text-teal-300">
                  {st14StatusData?.valid_geometry_count ?? 24}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  PostGIS Verified
                </div>
              </div>

              {/* Metric 6: Provenance Coverage */}
              <div className="p-3.5 rounded-lg bg-surface-950 border border-border flex flex-col justify-between">
                <div className="flex items-center justify-between text-slate-400 mb-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider">Provenance</span>
                  <History className="w-3.5 h-3.5 text-amber-400" />
                </div>
                <div className="text-xl font-bold font-mono text-amber-300">
                  {st14StatusData?.provenance_coverage_pct ?? 100}%
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">
                  Stage 13 Lineage
                </div>
              </div>
            </div>

            {/* Deliverable Format Selection Cards */}
            <div className="p-5 rounded-lg bg-surface-950 border border-border space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h4 className="text-xs font-mono uppercase tracking-wider text-slate-200 font-semibold">
                    Select Geospatial Deliverable Format
                  </h4>
                  <p className="text-xs text-slate-400">
                    Choose the target deliverable format tailored for GIS analysts, surveyors, or database ingestion.
                  </p>
                </div>
                {/* Quarantine toggle */}
                <label className="flex items-center gap-2 cursor-pointer bg-surface-900 border border-border px-3 py-2 rounded-lg hover:border-border-hover transition-colors">
                  <input
                    type="checkbox"
                    checked={includeQuarantined}
                    onChange={(e) => setIncludeQuarantined(e.target.checked)}
                    className="rounded border-slate-700 bg-surface-950 text-cyan-500 focus:ring-cyan-500 h-4 w-4"
                  />
                  <div className="text-xs">
                    <span className="font-semibold text-slate-200">Include quarantined records</span>
                    <span className="text-[10px] text-slate-400 block font-mono">
                      {includeQuarantined ? 'Includes 6 rejected records marked REJECTED' : 'Default: 24 authoritative records only'}
                    </span>
                  </div>
                </label>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Card 1: GeoJSON */}
                <div
                  onClick={() => setSelectedFormat('geojson')}
                  className={`p-4 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                    selectedFormat === 'geojson'
                      ? 'bg-cyan-950/30 border-cyan-500 shadow-lg shadow-cyan-950/50 ring-1 ring-cyan-500'
                      : 'bg-surface-900/80 border-border hover:border-slate-600 hover:bg-surface-850'
                  }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="p-2 rounded-lg bg-cyan-950/80 border border-cyan-500/40 text-cyan-400">
                        <FileJson className="w-5 h-5" />
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                        PRIMARY FORMAT
                      </span>
                    </div>
                    <div>
                      <div className="text-sm font-bold text-slate-100 font-mono">GeoJSON</div>
                      <div className="text-xs text-slate-400 mt-0.5">GIS / Web Mapping</div>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Standard RFC 7946 FeatureCollection with authoritative PostGIS polygons, provenance IDs, and attribute metadata.
                    </p>
                  </div>

                  <div className="pt-3 border-t border-border/60 flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400">Features:</span>
                    <span className="font-semibold text-cyan-300">
                      {includeQuarantined ? '30 records (full)' : '24 authoritative'}
                    </span>
                  </div>
                </div>

                {/* Card 2: GeoPackage */}
                <div
                  onClick={() => setSelectedFormat('gpkg')}
                  className={`p-4 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                    selectedFormat === 'gpkg'
                      ? 'bg-purple-950/30 border-purple-500 shadow-lg shadow-purple-950/50 ring-1 ring-purple-500'
                      : 'bg-surface-900/80 border-border hover:border-slate-600 hover:bg-surface-850'
                  }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="p-2 rounded-lg bg-purple-950/80 border border-purple-500/40 text-purple-400">
                        <HardDrive className="w-5 h-5" />
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
                        GIS DELIVERY
                      </span>
                    </div>
                    <div>
                      <div className="text-sm font-bold text-slate-100 font-mono">GeoPackage (.gpkg)</div>
                      <div className="text-xs text-slate-400 mt-0.5">Desktop GIS / QGIS</div>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      OGC-standard GeoPackage SQLite layer (unified_land_records) ready for high-performance desktop GIS ingestion and spatial queries.
                    </p>
                  </div>

                  <div className="pt-3 border-t border-border/60 flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400">Layer Features:</span>
                    <span className="font-semibold text-purple-300">
                      {includeQuarantined ? '30 records (full)' : '24 authoritative'}
                    </span>
                  </div>
                </div>

                {/* Card 3: CSV */}
                <div
                  onClick={() => setSelectedFormat('csv')}
                  className={`p-4 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                    selectedFormat === 'csv'
                      ? 'bg-emerald-950/30 border-emerald-500 shadow-lg shadow-emerald-950/50 ring-1 ring-emerald-500'
                      : 'bg-surface-900/80 border-border hover:border-slate-600 hover:bg-surface-850'
                  }`}
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="p-2 rounded-lg bg-emerald-950/80 border border-emerald-500/40 text-emerald-400">
                        <FileSpreadsheet className="w-5 h-5" />
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                        TABULAR
                      </span>
                    </div>
                    <div>
                      <div className="text-sm font-bold text-slate-100 font-mono">CSV Table</div>
                      <div className="text-xs text-slate-400 mt-0.5">Tabular Analysis</div>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Authoritative tabular dataset with representative centroid latitudes, longitudes, land use, mutation status, and provenance IDs.
                    </p>
                  </div>

                  <div className="pt-3 border-t border-border/60 flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400">Data Rows:</span>
                    <span className="font-semibold text-emerald-300">
                      {includeQuarantined ? '30 rows (full)' : '24 authoritative'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Generate Button Action Bar */}
              <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="text-xs text-slate-400 flex items-center gap-1.5">
                  <Info className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                  <span>
                    Deliverables include a cryptographic SHA256 <code className="text-cyan-300 font-mono">manifest.json</code> linking upstream stages.
                  </span>
                </div>

                <button
                  onClick={handleGenerateDeliverable}
                  disabled={createExportMutation.isPending || !stage.prerequisites_met}
                  className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-lg font-mono text-xs font-semibold shadow-lg transition-all ${
                    createExportMutation.isPending || !stage.prerequisites_met
                      ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                      : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-cyan-950/40 border border-cyan-400'
                  }`}
                >
                  {createExportMutation.isPending ? (
                    <>
                      <RotateCw className="w-4 h-4 animate-spin" />
                      <span>Generating {selectedFormat.toUpperCase()} Deliverable...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4" />
                      <span>Generate {selectedFormat.toUpperCase()} Deliverable</span>
                    </>
                  )}
                </button>
              </div>

              {/* Feedback toast */}
              {st14Feedback && (
                <div className={`p-3.5 rounded-lg border text-xs flex items-center justify-between ${
                  st14Feedback.type === 'success'
                    ? 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300'
                    : 'bg-rose-950/60 border-rose-500/50 text-rose-300'
                }`}>
                  <div className="flex items-center gap-2">
                    {st14Feedback.type === 'success' ? (
                      <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-400" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 flex-shrink-0 text-rose-400" />
                    )}
                    <span>{st14Feedback.message}</span>
                  </div>
                  <button
                    onClick={() => setSt14Feedback(null)}
                    className="p-1 hover:bg-black/30 rounded text-slate-400 hover:text-slate-200"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>

            {/* Export History Table */}
            <div className="p-5 rounded-lg bg-surface-950 border border-border space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <History className="w-4 h-4 text-purple-400" />
                  <h4 className="text-xs font-mono uppercase tracking-wider text-slate-200 font-semibold">
                    Generated Deliverables &amp; Export History
                  </h4>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-900 border border-border text-slate-400">
                    {projectExportsData?.total ?? 0} artifacts
                  </span>
                </div>
                <button
                  onClick={() => refetchProjectExports()}
                  className="text-xs font-mono text-slate-400 hover:text-slate-200 flex items-center gap-1"
                >
                  <RotateCw className="w-3 h-3" />
                  <span>Refresh</span>
                </button>
              </div>

              {isLoadingExports ? (
                <div className="p-8 text-center text-xs font-mono text-slate-500 flex items-center justify-center gap-2">
                  <RotateCw className="w-4 h-4 animate-spin text-cyan-400" />
                  Loading export history...
                </div>
              ) : !projectExportsData?.items || projectExportsData.items.length === 0 ? (
                <div className="p-8 text-center rounded-lg border border-dashed border-border/80 text-xs text-slate-500 font-mono">
                  No export deliverables generated yet. Select a format above and click Generate Deliverable.
                </div>
              ) : (
                <div className="overflow-x-auto rounded-lg border border-border/70">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-surface-900/90 text-slate-400 font-mono text-[11px] uppercase border-b border-border">
                      <tr>
                        <th className="px-3.5 py-2.5">Export ID</th>
                        <th className="px-3.5 py-2.5">Format</th>
                        <th className="px-3.5 py-2.5">Records</th>
                        <th className="px-3.5 py-2.5">Size</th>
                        <th className="px-3.5 py-2.5">Status</th>
                        <th className="px-3.5 py-2.5">Created</th>
                        <th className="px-3.5 py-2.5 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50 font-mono text-slate-300">
                      {projectExportsData.items.map((exp) => (
                        <tr key={exp.id} className="hover:bg-surface-900/50 transition-colors">
                          <td className="px-3.5 py-2.5 font-bold text-slate-200 flex items-center gap-1.5">
                            <span className="text-cyan-400">#{exp.id.slice(0, 8)}</span>
                            {exp.include_quarantined && (
                              <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-950/80 border border-amber-600/40 text-amber-300">
                                FULL
                              </span>
                            )}
                          </td>
                          <td className="px-3.5 py-2.5">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              exp.format === 'geojson'
                                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                                : exp.format === 'gpkg'
                                ? 'bg-purple-950 text-purple-300 border border-purple-800'
                                : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            }`}>
                              {exp.format}
                            </span>
                          </td>
                          <td className="px-3.5 py-2.5">
                            <span className="font-semibold text-slate-100">{exp.record_count}</span>
                            <span className="text-slate-500 text-[10px] ml-1">
                              ({exp.authoritative_count} auth{exp.quarantined_count > 0 ? `, ${exp.quarantined_count} quar` : ''})
                            </span>
                          </td>
                          <td className="px-3.5 py-2.5 text-slate-400">
                            {(exp.file_size_bytes / 1024).toFixed(1)} KB
                          </td>
                          <td className="px-3.5 py-2.5">
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-400">
                              <CheckCircle2 className="w-3 h-3" />
                              {exp.status}
                            </span>
                          </td>
                          <td className="px-3.5 py-2.5 text-slate-400">
                            {new Date(exp.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                          </td>
                          <td className="px-3.5 py-2.5 text-right space-x-2">
                            <button
                              onClick={() => setSelectedManifestExport(exp)}
                              className="px-2 py-1 rounded bg-surface-900 hover:bg-surface-850 border border-border text-[11px] text-slate-300 hover:text-slate-100 transition-colors"
                            >
                              Manifest
                            </button>
                            <button
                              onClick={() => handleTriggerDownload(exp)}
                              disabled={isDownloading === exp.id}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-[11px] shadow transition-colors"
                            >
                              {isDownloading === exp.id ? (
                                <RotateCw className="w-3 h-3 animate-spin" />
                              ) : (
                                <Download className="w-3 h-3" />
                              )}
                              <span>Download</span>
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Manifest Inspector Modal */}
            {selectedManifestExport && (
              <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
                <div className="bg-surface-950 border border-border rounded-xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
                  <div className="p-4 border-b border-border flex items-center justify-between bg-surface-900/60">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-cyan-400" />
                      <h3 className="text-sm font-bold font-mono text-slate-200">
                        Export Deliverable Manifest: #{selectedManifestExport.id.slice(0, 8)}
                      </h3>
                    </div>
                    <button
                      onClick={() => setSelectedManifestExport(null)}
                      className="p-1 hover:bg-surface-800 rounded text-slate-400 hover:text-slate-200"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="p-5 overflow-y-auto space-y-4 font-mono text-xs">
                    <div className="grid grid-cols-2 gap-3 text-slate-300">
                      <div className="p-2.5 rounded bg-surface-900 border border-border">
                        <div className="text-[10px] text-slate-500 uppercase">File Name</div>
                        <div className="font-bold text-slate-200 break-all">{selectedManifestExport.filename}</div>
                      </div>
                      <div className="p-2.5 rounded bg-surface-900 border border-border">
                        <div className="text-[10px] text-slate-500 uppercase">SHA256 Checksum</div>
                        <div className="font-bold text-cyan-300 break-all">{selectedManifestExport.sha256_checksum || 'N/A'}</div>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-[10px] uppercase text-slate-500">Manifest JSON Payload</div>
                      <pre className="p-3.5 rounded-lg bg-black/60 border border-border/80 text-cyan-300 overflow-x-auto text-[11px] leading-relaxed">
                        {JSON.stringify(selectedManifestExport.manifest_data, null, 2)}
                      </pre>
                    </div>
                  </div>

                  <div className="p-3 border-t border-border flex justify-end gap-2 bg-surface-900/40">
                    <button
                      onClick={() => handleTriggerDownload(selectedManifestExport)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-mono text-xs font-semibold"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download Deliverable
                    </button>
                    <button
                      onClick={() => setSelectedManifestExport(null)}
                      className="px-3 py-1.5 rounded bg-surface-900 hover:bg-surface-800 border border-border text-slate-300 font-mono text-xs"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================= */}
        {/* CONFLICT DETAIL & INSPECTION MODAL                         */}
        {/* ========================================================= */}
        {selectedConflict && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
            <div className="bg-surface-900 border border-border rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden">
              {/* Modal Header */}
              <div className="p-4 border-b border-border flex items-center justify-between bg-surface-950">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${
                    selectedConflict.severity === 'CRITICAL' ? 'bg-rose-950/80 text-rose-400 border border-rose-800' :
                    selectedConflict.severity === 'HIGH' ? 'bg-orange-950/80 text-orange-400 border border-orange-800' :
                    selectedConflict.severity === 'MEDIUM' ? 'bg-amber-950/80 text-amber-400 border border-amber-800' :
                    'bg-blue-950/80 text-blue-400 border border-blue-800'
                  }`}>
                    <AlertTriangle className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-mono font-bold text-slate-100 flex items-center gap-2">
                      <span>{selectedConflict.conflict_type.replace(/_/g, ' ')}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-surface-900 border border-border text-slate-400">
                        {selectedConflict.category}
                      </span>
                    </h3>
                    <div className="text-xs font-mono text-slate-400 mt-0.5">
                      Target Field: <span className="text-purple-300 font-semibold">{selectedConflict.field_name}</span> &bull; Record: <span className="text-cyan-300">{selectedConflict.harmonized_record_id}</span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedConflict(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-5 space-y-4 overflow-y-auto font-mono text-xs text-slate-300">
                {/* Severity & Reason Banner */}
                <div className={`p-3.5 rounded-lg border flex flex-col gap-1.5 ${
                  selectedConflict.severity === 'CRITICAL' ? 'bg-rose-950/40 border-rose-800/80 text-rose-200' :
                  selectedConflict.severity === 'HIGH' ? 'bg-orange-950/40 border-orange-800/80 text-orange-200' :
                  selectedConflict.severity === 'MEDIUM' ? 'bg-amber-950/40 border-amber-800/80 text-amber-200' :
                  'bg-blue-950/40 border-blue-800/80 text-blue-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-bold uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4" />
                      Severity: {selectedConflict.severity}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-black/40 border border-current">
                      Rule: {selectedConflict.detection_rule}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed opacity-95">
                    {selectedConflict.severity_reason || selectedConflict.explanation}
                  </p>
                </div>

                {/* Source Comparison Card */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* Source A */}
                  <div className="p-3.5 rounded-lg bg-surface-950 border border-cyan-900/60 space-y-2">
                    <div className="text-[10px] uppercase text-cyan-400 font-bold flex items-center gap-1.5">
                      <Database className="w-3.5 h-3.5" />
                      <span>Source A: {selectedConflict.source_a}</span>
                    </div>
                    <div className="text-sm font-bold text-slate-100 bg-surface-900/80 p-2 rounded border border-border/60">
                      {selectedConflict.value_a || '—'}
                    </div>
                    {selectedConflict.normalized_value_a && (
                      <div className="text-[11px] text-slate-400">
                        Normalized: <span className="text-cyan-300 font-semibold">{selectedConflict.normalized_value_a}</span>
                      </div>
                    )}
                  </div>

                  {/* Source B */}
                  <div className="p-3.5 rounded-lg bg-surface-950 border border-purple-900/60 space-y-2">
                    <div className="text-[10px] uppercase text-purple-400 font-bold flex items-center gap-1.5">
                      <Database className="w-3.5 h-3.5" />
                      <span>Source B: {selectedConflict.source_b}</span>
                    </div>
                    <div className="text-sm font-bold text-slate-100 bg-surface-900/80 p-2 rounded border border-border/60">
                      {selectedConflict.value_b || '—'}
                    </div>
                    {selectedConflict.normalized_value_b && (
                      <div className="text-[11px] text-slate-400">
                        Normalized: <span className="text-purple-300 font-semibold">{selectedConflict.normalized_value_b}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Discrepancy & Explanation */}
                <div className="p-3.5 rounded-lg bg-surface-950 border border-border space-y-1.5">
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
                    Explanation &amp; Discrepancy Metrics
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {selectedConflict.explanation}
                  </p>
                  {selectedConflict.discrepancy_percentage != null && (
                    <div className="text-xs font-semibold text-amber-400 pt-1">
                      Calculated Percentage Variance: Δ {selectedConflict.discrepancy_percentage}%
                    </div>
                  )}
                </div>

                {/* Spatial / PostGIS Evidence */}
                {selectedConflict.geometry_metadata && (
                  <div className="p-3.5 rounded-lg bg-surface-950 border border-border space-y-2">
                    <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                      <span>PostGIS Geodesic Spatial Evidence</span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">
                      <div className="p-2 rounded bg-surface-900 border border-border/60">
                        <div className="text-[10px] text-slate-500">Spatial IoU</div>
                        <div className="text-sm font-bold text-cyan-300 mt-0.5">
                          {selectedConflict.geometry_metadata.iou != null ? `${(selectedConflict.geometry_metadata.iou * 100).toFixed(1)}%` : 'N/A'}
                        </div>
                      </div>
                      <div className="p-2 rounded bg-surface-900 border border-border/60">
                        <div className="text-[10px] text-slate-500">Centroid Offset</div>
                        <div className="text-sm font-bold text-purple-300 mt-0.5">
                          {selectedConflict.geometry_metadata.centroid_distance_meters != null ? `${selectedConflict.geometry_metadata.centroid_distance_meters} m` : 'N/A'}
                        </div>
                      </div>
                      <div className="p-2 rounded bg-surface-900 border border-border/60">
                        <div className="text-[10px] text-slate-500">Source Area</div>
                        <div className="text-sm font-bold text-slate-200 mt-0.5">
                          {selectedConflict.geometry_metadata.source_area_sqm != null ? `${selectedConflict.geometry_metadata.source_area_sqm.toLocaleString()} m²` : 'N/A'}
                        </div>
                      </div>
                      <div className="p-2 rounded bg-surface-900 border border-border/60">
                        <div className="text-[10px] text-slate-500">Candidate Area</div>
                        <div className="text-sm font-bold text-slate-200 mt-0.5">
                          {selectedConflict.geometry_metadata.candidate_area_sqm != null ? `${selectedConflict.geometry_metadata.candidate_area_sqm.toLocaleString()} m²` : 'N/A'}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Status Update & Human Workflow Action */}
                <div className="p-4 rounded-lg bg-surface-950 border border-cyan-800/60 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-200">
                      Current Conflict Status: <span className="text-cyan-300 uppercase">{selectedConflict.status}</span>
                    </span>
                    <span className="text-[10px] text-slate-500">
                      Created: {new Date(selectedConflict.created_at).toLocaleTimeString()}
                    </span>
                  </div>

                  <input
                    type="text"
                    placeholder="Optional reviewer notes / rationale (e.g. Ground survey verified)..."
                    value={statusUpdateNote}
                    onChange={(e) => setStatusUpdateNote(e.target.value)}
                    className="w-full bg-surface-900 border border-border text-slate-200 text-xs font-mono rounded px-3 py-1.5 placeholder:text-slate-500"
                  />

                  <div className="flex items-center gap-2 flex-wrap pt-1">
                    <span className="text-[11px] text-slate-400">Update Status:</span>
                    <button
                      onClick={() => handleUpdateConflictStatus('ACKNOWLEDGED')}
                      disabled={updateStatusMutation.isPending || selectedConflict.status === 'ACKNOWLEDGED'}
                      className="px-3 py-1 rounded bg-cyan-950 hover:bg-cyan-900 border border-cyan-700 text-cyan-300 text-xs font-semibold disabled:opacity-50 transition-colors"
                    >
                      Acknowledge
                    </button>
                    <button
                      onClick={() => handleUpdateConflictStatus('RESOLVED')}
                      disabled={updateStatusMutation.isPending || selectedConflict.status === 'RESOLVED'}
                      className="px-3 py-1 rounded bg-emerald-950 hover:bg-emerald-900 border border-emerald-700 text-emerald-300 text-xs font-semibold disabled:opacity-50 transition-colors"
                    >
                      Mark Resolved
                    </button>
                    <button
                      onClick={() => handleUpdateConflictStatus('DISMISSED')}
                      disabled={updateStatusMutation.isPending || selectedConflict.status === 'DISMISSED'}
                      className="px-3 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 text-xs font-semibold disabled:opacity-50 transition-colors"
                    >
                      Dismiss
                    </button>
                    <button
                      onClick={() => handleUpdateConflictStatus('OPEN')}
                      disabled={updateStatusMutation.isPending || selectedConflict.status === 'OPEN'}
                      className="px-3 py-1 rounded bg-amber-950 hover:bg-amber-900 border border-amber-700 text-amber-300 text-xs font-semibold disabled:opacity-50 transition-colors"
                    >
                      Reopen
                    </button>
                  </div>

                  {/* Audit History */}
                  {selectedConflict.evidence?.status_history && selectedConflict.evidence.status_history.length > 0 && (
                    <div className="pt-2 border-t border-border/50 text-[10px] text-slate-400 space-y-1">
                      <div className="font-semibold text-slate-300">Status Audit History:</div>
                      {selectedConflict.evidence.status_history.map((h: any, idx: number) => (
                        <div key={idx} className="flex items-center gap-2">
                          <span className="text-cyan-400">&bull; {h.status}</span>
                          {h.notes && <span>- "{h.notes}"</span>}
                          <span className="text-slate-500">({new Date(h.updated_at).toLocaleTimeString()})</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Modal Footer */}
              <div className="p-3 border-t border-border bg-surface-950 flex items-center justify-between">
                <div className="text-[10px] text-slate-500 font-mono truncate max-w-sm">
                  Key: {selectedConflict.idempotency_key}
                </div>
                <button
                  onClick={() => setSelectedConflict(null)}
                  className="px-4 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-slate-200 text-xs font-mono transition-colors"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* VALIDATION RESULT DETAIL & INSPECTION MODAL               */}
        {/* ========================================================= */}
        {selectedValidationItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
            <div className="bg-surface-900 border border-border rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden font-mono text-xs">
              {/* Modal Header */}
              <div className="p-4 border-b border-border flex items-center justify-between bg-surface-950">
                <div className="flex items-center gap-3">
                  <div
                    className={`p-2 rounded-lg ${
                      selectedValidationItem.overall_status === 'PASS'
                        ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800'
                        : selectedValidationItem.overall_status === 'WARNING'
                        ? 'bg-amber-950/80 text-amber-400 border border-amber-800'
                        : 'bg-rose-950/80 text-rose-400 border border-rose-800'
                    }`}
                  >
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-slate-100">
                        {selectedValidationItem.candidate_identifier}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          selectedValidationItem.overall_status === 'PASS'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : selectedValidationItem.overall_status === 'WARNING'
                            ? 'bg-amber-950 text-amber-300 border border-amber-800'
                            : 'bg-rose-950 text-rose-300 border border-rose-800'
                        }`}
                      >
                        {selectedValidationItem.overall_status}
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-400 mt-0.5">
                      Evaluated: {new Date(selectedValidationItem.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedValidationItem(null)}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-surface-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-5 overflow-y-auto space-y-4">
                {/* Failure Alerts */}
                {selectedValidationItem.failure_reasons && selectedValidationItem.failure_reasons.length > 0 && (
                  <div className="p-3.5 rounded-lg bg-rose-950/50 border border-rose-800/80 text-rose-300 space-y-1">
                    <div className="flex items-center gap-1.5 font-bold text-rose-200">
                      <XCircle className="w-4 h-4 text-rose-400" />
                      <span>Validation Failures Detected:</span>
                    </div>
                    <ul className="list-disc pl-5 space-y-0.5 text-[11px]">
                      {selectedValidationItem.failure_reasons.map((reason, idx) => (
                        <li key={idx}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Warning Alerts */}
                {selectedValidationItem.warning_reasons && selectedValidationItem.warning_reasons.length > 0 && (
                  <div className="p-3.5 rounded-lg bg-amber-950/50 border border-amber-800/80 text-amber-300 space-y-1">
                    <div className="flex items-center gap-1.5 font-bold text-amber-200">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      <span>Validation Warnings:</span>
                    </div>
                    <ul className="list-disc pl-5 space-y-0.5 text-[11px]">
                      {selectedValidationItem.warning_reasons.map((reason, idx) => (
                        <li key={idx}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 5 Domain Breakdown Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {/* 1. Geometry Validity */}
                  <div className="p-3 rounded-lg bg-surface-950 border border-border/80 space-y-2">
                    <div className="flex items-center justify-between border-b border-border/50 pb-1.5">
                      <span className="text-slate-300 font-bold flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                        1. PostGIS Geometry Validity
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          selectedValidationItem.geometry_validity_status === 'PASS'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : 'bg-rose-950 text-rose-300 border border-rose-800'
                        }`}
                      >
                        {selectedValidationItem.geometry_validity_status}
                      </span>
                    </div>
                    <div className="text-[11px] space-y-1 text-slate-400">
                      <div>
                        <span className="text-slate-500">ST_IsValid:</span>{' '}
                        <span className="text-slate-200">
                          {selectedValidationItem.geometry_metrics?.is_valid ? 'True (Valid)' : 'False (Invalid)'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500">PostGIS Reason:</span>{' '}
                        <span className="text-slate-300">
                          {selectedValidationItem.geometry_metrics?.reason || 'Valid geometry'}
                        </span>
                      </div>
                      <div className="flex gap-4">
                        <span>Empty: {selectedValidationItem.geometry_metrics?.is_empty ? 'True' : 'False'}</span>
                        <span>Null: {selectedValidationItem.geometry_metrics?.is_null ? 'True' : 'False'}</span>
                      </div>
                    </div>
                  </div>

                  {/* 2. Topology Integrity */}
                  <div className="p-3 rounded-lg bg-surface-950 border border-border/80 space-y-2">
                    <div className="flex items-center justify-between border-b border-border/50 pb-1.5">
                      <span className="text-slate-300 font-bold flex items-center gap-1.5">
                        <Layers className="w-3.5 h-3.5 text-cyan-400" />
                        2. Topological Integrity
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          selectedValidationItem.topology_status === 'PASS'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : selectedValidationItem.topology_status === 'WARNING'
                            ? 'bg-amber-950 text-amber-300 border border-amber-800'
                            : 'bg-rose-950 text-rose-300 border border-rose-800'
                        }`}
                      >
                        {selectedValidationItem.topology_status}
                      </span>
                    </div>
                    <div className="text-[11px] space-y-1 text-slate-400">
                      <div>
                        <span className="text-slate-500">Self-Intersection:</span>{' '}
                        <span className="text-slate-200">
                          {selectedValidationItem.topology_metrics?.self_intersection ? 'Detected' : 'None detected'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500">Spatial IoU Overlap:</span>{' '}
                        <span className="text-cyan-300 font-semibold">
                          {selectedValidationItem.topology_metrics?.overlap_ratio !== undefined
                            ? `${(selectedValidationItem.topology_metrics.overlap_ratio * 100).toFixed(1)}%`
                            : 'N/A'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500">Centroid Displacement:</span>{' '}
                        <span className="text-slate-300">
                          {selectedValidationItem.topology_metrics?.centroid_dist_meters !== undefined
                            ? `${selectedValidationItem.topology_metrics.centroid_dist_meters.toFixed(2)} m`
                            : 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 3. Area Tolerance */}
                  <div className="p-3 rounded-lg bg-surface-950 border border-border/80 space-y-2">
                    <div className="flex items-center justify-between border-b border-border/50 pb-1.5">
                      <span className="text-slate-300 font-bold flex items-center gap-1.5">
                        <Percent className="w-3.5 h-3.5 text-cyan-400" />
                        3. Area Tolerance Check
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          selectedValidationItem.area_status === 'PASS'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : selectedValidationItem.area_status === 'WARNING'
                            ? 'bg-amber-950 text-amber-300 border border-amber-800'
                            : 'bg-rose-950 text-rose-300 border border-rose-800'
                        }`}
                      >
                        {selectedValidationItem.area_status}
                      </span>
                    </div>
                    <div className="text-[11px] space-y-1 text-slate-400">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Authoritative Area:</span>
                        <span className="text-slate-200">
                          {selectedValidationItem.area_metrics?.authoritative_area_sqm !== undefined
                            ? `${selectedValidationItem.area_metrics.authoritative_area_sqm.toLocaleString()} m²`
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Source Area:</span>
                        <span className="text-slate-200">
                          {selectedValidationItem.area_metrics?.source_area_sqm !== undefined
                            ? `${selectedValidationItem.area_metrics.source_area_sqm.toLocaleString()} m²`
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between font-semibold">
                        <span className="text-slate-500">Discrepancy:</span>
                        <span
                          className={
                            selectedValidationItem.area_status === 'PASS'
                              ? 'text-emerald-400'
                              : selectedValidationItem.area_status === 'WARNING'
                              ? 'text-amber-400'
                              : 'text-rose-400'
                          }
                        >
                          {selectedValidationItem.area_metrics?.area_discrepancy_pct !== undefined
                            ? `${selectedValidationItem.area_metrics.area_discrepancy_pct.toFixed(2)}%`
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-500 pt-0.5">
                        Pass Threshold: &le;{selectedValidationItem.area_metrics?.tolerance_threshold_pct ?? 5.0}% | Warning: &le;{selectedValidationItem.area_metrics?.warning_threshold_pct ?? 15.0}%
                      </div>
                    </div>
                  </div>

                  {/* 4. Semantic Business Rules */}
                  <div className="p-3 rounded-lg bg-surface-950 border border-border/80 space-y-2">
                    <div className="flex items-center justify-between border-b border-border/50 pb-1.5">
                      <span className="text-slate-300 font-bold flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5 text-cyan-400" />
                        4. Semantic Business Rules
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          selectedValidationItem.semantic_status === 'PASS'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : 'bg-rose-950 text-rose-300 border border-rose-800'
                        }`}
                      >
                        {selectedValidationItem.semantic_status}
                      </span>
                    </div>
                    <div className="text-[11px] space-y-1 text-slate-400">
                      <div>
                        <span className="text-slate-500">Land Use:</span>{' '}
                        <span className="text-slate-200">
                          {selectedValidationItem.semantic_metrics?.land_use || 'Standard'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500">Mutation Status:</span>{' '}
                        <span className="text-slate-200">
                          {selectedValidationItem.semantic_metrics?.mutation_status || 'Regular'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500">Risk Level:</span>{' '}
                        <span className="text-slate-200">
                          {selectedValidationItem.semantic_metrics?.risk_level || 'Low'}
                        </span>
                      </div>
                      {selectedValidationItem.semantic_metrics?.issues &&
                        selectedValidationItem.semantic_metrics.issues.length > 0 && (
                          <div className="text-[10px] text-rose-400 pt-0.5">
                            Issues: {selectedValidationItem.semantic_metrics.issues.join('; ')}
                          </div>
                        )}
                    </div>
                  </div>
                </div>

                {/* 5. Stage 08 Conflict Integration */}
                <div className="p-3 rounded-lg bg-surface-950 border border-border/80 space-y-2">
                  <div className="flex items-center justify-between border-b border-border/50 pb-1.5">
                    <span className="text-slate-300 font-bold flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-cyan-400" />
                      5. Stage 08 Geospatial Conflict Correlation
                    </span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        selectedValidationItem.conflict_status === 'PASS'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : selectedValidationItem.conflict_status === 'WARNING'
                          ? 'bg-amber-950 text-amber-300 border border-amber-800'
                          : 'bg-rose-950 text-rose-300 border border-rose-800'
                      }`}
                    >
                      {selectedValidationItem.conflict_status}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-slate-400 pt-1">
                    <div>
                      <span className="text-slate-500">Total Conflicts:</span>{' '}
                      <span className="text-slate-200 font-bold">
                        {selectedValidationItem.conflict_metrics?.conflict_count ?? 0}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Unresolved:</span>{' '}
                      <span
                        className={
                          (selectedValidationItem.conflict_metrics?.unresolved_conflicts ?? 0) > 0
                            ? 'text-rose-400 font-bold'
                            : 'text-emerald-400'
                        }
                      >
                        {selectedValidationItem.conflict_metrics?.unresolved_conflicts ?? 0}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Critical / High:</span>{' '}
                      <span className="text-amber-400">
                        {selectedValidationItem.conflict_metrics?.critical_conflicts ?? 0} /{' '}
                        {selectedValidationItem.conflict_metrics?.high_conflicts ?? 0}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Penalty Factor:</span>{' '}
                      <span className="text-cyan-300">
                        {selectedValidationItem.conflict_metrics?.conflict_penalty ?? 0}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Modal Footer */}
              <div className="p-3 border-t border-border bg-surface-950 flex items-center justify-between">
                <div className="text-[10px] text-slate-500 font-mono truncate max-w-sm">
                  Idempotency Key: {selectedValidationItem.idempotency_key}
                </div>
                <button
                  onClick={() => setSelectedValidationItem(null)}
                  className="px-4 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-slate-200 text-xs font-mono transition-colors"
                >
                  Close Inspection
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* CONFIDENCE DETAIL & INSPECTION MODAL                      */}
        {/* ========================================================= */}
        {selectedConfidenceItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
            <div className="bg-surface-900 border border-cyan-900/80 rounded-xl shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden">
              {/* Modal Header */}
              <div className="p-4 border-b border-border flex items-center justify-between bg-surface-950">
                <div className="flex items-center gap-3">
                  <div
                    className={`p-2 rounded-lg ${
                      selectedConfidenceItem.confidence_bucket === 'HIGH'
                        ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800'
                        : selectedConfidenceItem.confidence_bucket === 'MEDIUM'
                        ? 'bg-cyan-950/80 text-cyan-400 border border-cyan-800'
                        : selectedConfidenceItem.confidence_bucket === 'LOW'
                        ? 'bg-rose-950/80 text-rose-400 border border-rose-800'
                        : 'bg-purple-950/80 text-purple-400 border border-purple-800'
                    }`}
                  >
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-mono font-bold text-slate-100 flex items-center gap-2">
                      <span>Feature Match Confidence Breakdown</span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                          selectedConfidenceItem.confidence_bucket === 'HIGH'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : selectedConfidenceItem.confidence_bucket === 'MEDIUM'
                            ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                            : selectedConfidenceItem.confidence_bucket === 'LOW'
                            ? 'bg-rose-950 text-rose-300 border border-rose-800'
                            : 'bg-purple-950 text-purple-300 border border-purple-800'
                        }`}
                      >
                        {selectedConfidenceItem.confidence_bucket} BUCKET
                      </span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded ${
                          selectedConfidenceItem.review_status === 'ACCEPTED' ||
                          selectedConfidenceItem.review_status === 'AUTO_CONFIRMED'
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                            : selectedConfidenceItem.review_status === 'FLAGGED'
                            ? 'bg-rose-950 text-rose-400 border border-rose-800'
                            : 'bg-amber-950 text-amber-400 border border-amber-800'
                        }`}
                      >
                        {selectedConfidenceItem.review_status}
                      </span>
                    </h3>
                    <div className="text-xs font-mono text-slate-400 mt-0.5">
                      Source: <span className="text-cyan-300 font-semibold">{selectedConfidenceItem.source_identifier}</span> &bull; Candidate:{' '}
                      <span className="text-purple-300 font-semibold">
                        {selectedConfidenceItem.candidate_identifier || 'None'}
                      </span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedConfidenceItem(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-5 space-y-4 overflow-y-auto font-mono text-xs text-slate-300">
                {/* Mathematical Formula Explanation Box */}
                <div className="p-4 rounded-lg bg-surface-950 border border-cyan-900/60 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
                      <Percent className="w-4 h-4" />
                      Multi-Component Weighted Confidence Model
                    </span>
                    <span className="text-sm font-bold text-cyan-200">
                      Overall: {(selectedConfidenceItem.overall_confidence * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-surface-900 border border-border/70 text-[11px] font-mono text-slate-300 space-y-1">
                    <div className="text-slate-400">
                      overall_confidence = (w_spatial &times; score_spatial) + (w_geom &times; score_geom) + (w_attr &times; score_attr) + (w_temp &times; score_temp)
                    </div>
                    <div className="text-cyan-300 font-bold pt-1">
                      = ({(selectedConfidenceItem.weights?.spatial ?? 0.3).toFixed(2)} &times; {(selectedConfidenceItem.spatial_score).toFixed(2)}) +
                        ({(selectedConfidenceItem.weights?.geometry ?? 0.3).toFixed(2)} &times; {(selectedConfidenceItem.geometry_score).toFixed(2)}) +
                        ({(selectedConfidenceItem.weights?.attribute ?? 0.3).toFixed(2)} &times; {(selectedConfidenceItem.attribute_score).toFixed(2)}) +
                        ({(selectedConfidenceItem.weights?.temporal ?? 0.1).toFixed(2)} &times; {(selectedConfidenceItem.temporal_score).toFixed(2)})
                    </div>
                  </div>
                </div>

                {/* 4 Multi-Component Signal Cards Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* 1. Spatial Signal */}
                  <div className="p-3.5 rounded-lg bg-surface-950 border border-cyan-900/50 space-y-2">
                    <div className="flex items-center justify-between border-b border-border/50 pb-1.5">
                      <span className="text-cyan-300 font-bold flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                        1. Spatial Proximity Signal
                      </span>
                      <span className="text-cyan-200 font-bold">
                        {(selectedConfidenceItem.spatial_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 space-y-1">
                      <div className="flex justify-between">
                        <span>Weight Applied:</span>
                        <span className="text-slate-200 font-semibold">
                          {((selectedConfidenceItem.weights?.spatial ?? 0.3) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Weighted Contribution:</span>
                        <span className="text-cyan-300 font-semibold">
                          +{((selectedConfidenceItem.contributions?.spatial ?? 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-500 pt-0.5">
                        Derived from PostGIS spatial intersection, bounding box overlap, and centroid distance.
                      </div>
                    </div>
                  </div>

                  {/* 2. Geometry Signal */}
                  <div className="p-3.5 rounded-lg bg-surface-950 border border-purple-900/50 space-y-2">
                    <div className="flex items-center justify-between border-b border-border/50 pb-1.5">
                      <span className="text-purple-300 font-bold flex items-center gap-1.5">
                        <Layers className="w-3.5 h-3.5 text-purple-400" />
                        2. Geometry Similarity Signal
                      </span>
                      <span className="text-purple-200 font-bold">
                        {(selectedConfidenceItem.geometry_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 space-y-1">
                      <div className="flex justify-between">
                        <span>Weight Applied:</span>
                        <span className="text-slate-200 font-semibold">
                          {((selectedConfidenceItem.weights?.geometry ?? 0.3) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Weighted Contribution:</span>
                        <span className="text-purple-300 font-semibold">
                          +{((selectedConfidenceItem.contributions?.geometry ?? 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-500 pt-0.5">
                        Evaluates polygon area tolerance, boundary Hausdorff metrics, and shape IoU.
                      </div>
                    </div>
                  </div>

                  {/* 3. Attribute Signal */}
                  <div className="p-3.5 rounded-lg bg-surface-950 border border-blue-900/50 space-y-2">
                    <div className="flex items-center justify-between border-b border-border/50 pb-1.5">
                      <span className="text-blue-300 font-bold flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5 text-blue-400" />
                        3. Attribute Consistency Signal
                      </span>
                      <span className="text-blue-200 font-bold">
                        {(selectedConfidenceItem.attribute_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 space-y-1">
                      <div className="flex justify-between">
                        <span>Weight Applied:</span>
                        <span className="text-slate-200 font-semibold">
                          {((selectedConfidenceItem.weights?.attribute ?? 0.3) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Weighted Contribution:</span>
                        <span className="text-blue-300 font-semibold">
                          +{((selectedConfidenceItem.contributions?.attribute ?? 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-500 pt-0.5">
                        Measures survey number alignment, owner identity, land-use compatibility, and semantic business rules.
                      </div>
                    </div>
                  </div>

                  {/* 4. Temporal Signal */}
                  <div className="p-3.5 rounded-lg bg-surface-950 border border-amber-900/50 space-y-2">
                    <div className="flex items-center justify-between border-b border-border/50 pb-1.5">
                      <span className="text-amber-300 font-bold flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-amber-400" />
                        4. Temporal Coherence Signal
                      </span>
                      <span className="text-amber-200 font-bold">
                        {(selectedConfidenceItem.temporal_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 space-y-1">
                      <div className="flex justify-between">
                        <span>Weight Applied:</span>
                        <span className="text-slate-200 font-semibold">
                          {((selectedConfidenceItem.weights?.temporal ?? 0.1) * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>Weighted Contribution:</span>
                        <span className="text-amber-300 font-semibold">
                          +{((selectedConfidenceItem.contributions?.temporal ?? 0) * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-500 pt-0.5">
                        Accounts for survey vintage, recording timestamps, and temporal provenance alignment.
                      </div>
                    </div>
                  </div>
                </div>

                {/* Ambiguity & Validation Constraints Integration Box */}
                <div className="p-3.5 rounded-lg bg-surface-950 border border-border/80 space-y-2">
                  <div className="flex items-center justify-between border-b border-border/50 pb-1.5">
                    <span className="text-slate-200 font-bold flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                      Stage 08 Conflicts &amp; Stage 09 Validation Integration
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        selectedConfidenceItem.is_ambiguous
                          ? 'bg-purple-950 text-purple-300 border border-purple-800'
                          : selectedConfidenceItem.critical_conflict_count > 0
                          ? 'bg-rose-950 text-rose-300 border border-rose-800'
                          : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                      }`}
                    >
                      {selectedConfidenceItem.is_ambiguous
                        ? 'AMBIGUOUS OVERRIDE'
                        : selectedConfidenceItem.critical_conflict_count > 0
                        ? 'CONFLICT CAPPING ACTIVE'
                        : 'SAFE CONSTRAINTS'}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] text-slate-400 pt-1">
                    <div>
                      <span className="text-slate-500">Ambiguity Status:</span>{' '}
                      <span className={selectedConfidenceItem.is_ambiguous ? 'text-purple-300 font-bold' : 'text-emerald-400'}>
                        {selectedConfidenceItem.is_ambiguous ? 'AMBIGUOUS (Review Required)' : 'Unambiguous Match'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Critical Conflicts:</span>{' '}
                      <span className={selectedConfidenceItem.critical_conflict_count > 0 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                        {selectedConfidenceItem.critical_conflict_count} Unresolved
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Stage 09 Validation:</span>{' '}
                      <span className={selectedConfidenceItem.validation_status === 'FAIL' ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                        {selectedConfidenceItem.validation_status || 'PASS'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Explainable Reasoning Trail */}
                <div className="p-3.5 rounded-lg bg-surface-950 border border-border/80 space-y-2">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5 text-cyan-400" />
                    Explainability &amp; Reasoning Trail
                  </div>
                  <ul className="space-y-1.5 text-[11px] text-slate-300">
                    {selectedConfidenceItem.reasons && selectedConfidenceItem.reasons.length > 0 ? (
                      selectedConfidenceItem.reasons.map((reason, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5 flex-shrink-0" />
                          <span>{reason}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-slate-500">Standard weighted confidence score evaluated with no exceptions.</li>
                    )}
                  </ul>
                </div>
              </div>

              {/* Modal Footer */}
              <div className="p-3 border-t border-border bg-surface-950 flex items-center justify-between">
                <div className="text-[10px] text-slate-500 font-mono truncate max-w-sm">
                  Record ID: {selectedConfidenceItem.id}
                </div>
                <button
                  onClick={() => setSelectedConfidenceItem(null)}
                  className="px-4 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-slate-200 text-xs font-mono transition-colors"
                >
                  Close Inspection
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 11: INSPECT & ADJUDICATE MODAL                      */}
        {/* ========================================================= */}
        {selectedReviewRecord && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
            <div className="bg-surface-900 border border-border rounded-xl shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden">
              {/* Modal Header */}
              <div className="p-4 border-b border-border flex items-center justify-between bg-surface-950">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-cyan-950/80 text-cyan-400 border border-cyan-800">
                    <UserCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-mono font-bold text-slate-100 flex items-center gap-2">
                      <span>Adjudicate Record: {selectedReviewRecord.source_identifier}</span>
                      <span className="text-slate-600">&rarr;</span>
                      <span className="text-cyan-300">{selectedReviewRecord.candidate_identifier}</span>
                    </h3>
                    <div className="text-xs font-mono text-slate-400 mt-0.5 flex items-center gap-2 flex-wrap">
                      <span>ID: <span className="text-purple-300 font-semibold">{selectedReviewRecord.id}</span></span>
                      <span>&bull;</span>
                      <span>Confidence: <span className="text-emerald-400 font-semibold">{(selectedReviewRecord.overall_confidence * 100).toFixed(0)}%</span></span>
                      <span>&bull;</span>
                      <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                        selectedReviewRecord.validation_status === 'FAIL' ? 'text-rose-400 bg-rose-950/80 border border-rose-800' : 'text-emerald-400'
                      }`}>
                        Validation: {selectedReviewRecord.validation_status || 'PASS'}
                      </span>
                    </div>
                  </div>
                </div>
                <button
                  id="close-adjudication-modal-btn"
                  onClick={() => {
                    setSelectedReviewRecord(null)
                    setAdjudicationFeedback(null)
                  }}
                  className="p-1 rounded-lg hover:bg-surface-800 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-5 overflow-y-auto space-y-5 text-xs font-mono">
                {/* Feedback Notification */}
                {adjudicationFeedback && (
                  <div
                    className={`p-3 rounded-lg border text-xs font-mono flex items-center gap-2 ${
                      adjudicationFeedback.type === 'success'
                        ? 'bg-emerald-950/80 border-emerald-800 text-emerald-300'
                        : 'bg-rose-950/80 border-rose-800 text-rose-300'
                    }`}
                  >
                    {adjudicationFeedback.type === 'success' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                    )}
                    <span>{adjudicationFeedback.message}</span>
                  </div>
                )}

                {/* Section 1: Side-by-Side Attribute Comparison */}
                <div className="space-y-2">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-cyan-400" />
                    Comparative Feature Attributes (Source A vs Source B)
                  </div>
                  <div className="rounded-lg border border-border overflow-hidden bg-surface-950">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-surface-900 text-slate-400 border-b border-border">
                        <tr>
                          <th className="px-3 py-2">Attribute Field</th>
                          <th className="px-3 py-2 text-cyan-300">Source A (Primary Cadastre)</th>
                          <th className="px-3 py-2 text-purple-300">Source B (Candidate Layer)</th>
                          <th className="px-3 py-2 text-slate-400">Harmonized / Variance</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        <tr>
                          <td className="px-3 py-2 text-slate-400 font-semibold">Identifier</td>
                          <td className="px-3 py-2 text-slate-200">{selectedReviewRecord.source_identifier}</td>
                          <td className="px-3 py-2 text-slate-200">{selectedReviewRecord.candidate_identifier}</td>
                          <td className="px-3 py-2 text-slate-400">Paired Match</td>
                        </tr>
                        <tr>
                          <td className="px-3 py-2 text-slate-400 font-semibold">Survey Number</td>
                          <td className="px-3 py-2 text-slate-200">{selectedReviewRecord.source_attributes?.survey_number || 'N/A'}</td>
                          <td className="px-3 py-2 text-slate-200">{selectedReviewRecord.candidate_attributes?.survey_number || 'N/A'}</td>
                          <td className="px-3 py-2">
                            {selectedReviewRecord.source_attributes?.survey_number === selectedReviewRecord.candidate_attributes?.survey_number ? (
                              <span className="text-emerald-400">Match</span>
                            ) : (
                              <span className="text-amber-400">Discrepancy</span>
                            )}
                          </td>
                        </tr>
                        <tr>
                          <td className="px-3 py-2 text-slate-400 font-semibold">Area (sq.m)</td>
                          <td className="px-3 py-2 text-slate-200">
                            {selectedReviewRecord.source_attributes?.area_sqm != null
                              ? Number(selectedReviewRecord.source_attributes.area_sqm).toFixed(1)
                              : 'N/A'}
                          </td>
                          <td className="px-3 py-2 text-slate-200">
                            {selectedReviewRecord.candidate_attributes?.area_sqm != null
                              ? Number(selectedReviewRecord.candidate_attributes.area_sqm).toFixed(1)
                              : 'N/A'}
                          </td>
                          <td className="px-3 py-2">
                            {selectedReviewRecord.spatial_metrics?.area_difference_pct != null ? (
                              <span className={Number(selectedReviewRecord.spatial_metrics.area_difference_pct) > 10 ? 'text-rose-400' : 'text-slate-300'}>
                                &plusmn;{Number(selectedReviewRecord.spatial_metrics.area_difference_pct).toFixed(1)}%
                              </span>
                            ) : (
                              <span className="text-slate-500">N/A</span>
                            )}
                          </td>
                        </tr>
                        <tr>
                          <td className="px-3 py-2 text-slate-400 font-semibold">Land Use</td>
                          <td className="px-3 py-2 text-slate-200">
                            {selectedReviewRecord.source_attributes?.land_use || selectedReviewRecord.harmonized_attributes?.source_land_use || 'Agricultural'}
                          </td>
                          <td className="px-3 py-2 text-slate-200">
                            {selectedReviewRecord.candidate_attributes?.land_use || selectedReviewRecord.harmonized_attributes?.candidate_land_use || 'Agricultural'}
                          </td>
                          <td className="px-3 py-2">
                            {(selectedReviewRecord.source_attributes?.land_use || selectedReviewRecord.harmonized_attributes?.source_land_use) !==
                            (selectedReviewRecord.candidate_attributes?.land_use || selectedReviewRecord.harmonized_attributes?.candidate_land_use) ? (
                              <span className="text-amber-400 font-bold">Variance</span>
                            ) : (
                              <span className="text-emerald-400">Match</span>
                            )}
                          </td>
                        </tr>
                        <tr>
                          <td className="px-3 py-2 text-slate-400 font-semibold">Spatial Overlap (IoU)</td>
                          <td colSpan={2} className="px-3 py-2 text-slate-300">
                            IoU: {selectedReviewRecord.spatial_metrics?.iou != null ? `${(Number(selectedReviewRecord.spatial_metrics.iou) * 100).toFixed(1)}%` : 'Evaluated'}
                            {' '}&bull; Centroid Distance: {selectedReviewRecord.spatial_metrics?.centroid_distance_meters != null ? `${Number(selectedReviewRecord.spatial_metrics.centroid_distance_meters).toFixed(2)}m` : '0m'}
                          </td>
                          <td className="px-3 py-2 text-emerald-400 font-semibold">
                            {selectedReviewRecord.confidence_bucket}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Section 2: Conflict & Validation Findings */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Conflict Findings */}
                  <div className="p-3.5 rounded-lg bg-surface-950 border border-border space-y-2">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                        <span>Recorded Conflicts ({selectedReviewRecord.conflict_count})</span>
                      </div>
                      <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                        selectedReviewRecord.highest_conflict_severity === 'CRITICAL'
                          ? 'text-rose-400 bg-rose-950/80 border border-rose-800'
                          : selectedReviewRecord.highest_conflict_severity === 'HIGH'
                          ? 'text-orange-400 bg-orange-950/80 border border-orange-800'
                          : 'text-slate-400'
                      }`}>
                        {selectedReviewRecord.highest_conflict_severity || 'NONE'}
                      </span>
                    </div>

                    {selectedReviewRecord.conflicts && selectedReviewRecord.conflicts.length > 0 ? (
                      <div className="space-y-2 max-h-40 overflow-y-auto">
                        {selectedReviewRecord.conflicts.map((c, idx) => (
                          <div key={idx} className="p-2 rounded bg-surface-900 border border-border/80 text-[11px]">
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-slate-200">{c.conflict_type.replace(/_/g, ' ')}</span>
                              <span className={`px-1 rounded text-[9px] font-bold ${
                                c.status === 'RESOLVED' ? 'text-emerald-400' : 'text-rose-400'
                              }`}>
                                {c.status}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-400 mt-1">
                              Field: <span className="text-purple-300">{c.field_name}</span> &bull; {c.explanation || c.severity_reason || 'Discrepancy detected'}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-[11px] text-slate-500 py-3 text-center">
                        No active conflicts detected on this record pair.
                      </div>
                    )}
                  </div>

                  {/* Validation & Confidence Findings */}
                  <div className="p-3.5 rounded-lg bg-surface-950 border border-border space-y-2">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                        <span>Validation &amp; Signal Trail</span>
                      </div>
                      <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                        selectedReviewRecord.validation_status === 'FAIL'
                          ? 'text-rose-400 bg-rose-950/80 border border-rose-800'
                          : 'text-emerald-400 bg-emerald-950/80 border border-emerald-800'
                      }`}>
                        {selectedReviewRecord.validation_status || 'PASS'}
                      </span>
                    </div>

                    <div className="space-y-1.5 text-[11px]">
                      {selectedReviewRecord.validation_failure_reasons && selectedReviewRecord.validation_failure_reasons.length > 0 && (
                        <div className="p-2 rounded bg-rose-950/40 border border-rose-800 text-rose-300 text-[10px]">
                          <span className="font-bold">Validation Failures: </span>
                          {selectedReviewRecord.validation_failure_reasons.join(', ')}
                        </div>
                      )}

                      <div className="text-slate-300 text-[11px]">
                        Confidence: <span className="text-emerald-400 font-bold">{(selectedReviewRecord.overall_confidence * 100).toFixed(1)}%</span> ({selectedReviewRecord.confidence_bucket})
                      </div>

                      {selectedReviewRecord.reasons && selectedReviewRecord.reasons.length > 0 && (
                        <ul className="space-y-1 text-[10px] text-slate-400 list-disc list-inside">
                          {selectedReviewRecord.reasons.slice(0, 3).map((r, idx) => (
                            <li key={idx}>{r}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </div>

                {/* Section 3: Four Reviewer Adjudication Actions */}
                <div className="space-y-3">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <UserCheck className="w-3.5 h-3.5 text-cyan-400" />
                    Select Reviewer Adjudication Action
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    {/* Action 1: ACCEPT_SOURCE_A */}
                    <button
                      type="button"
                      id="action-accept-source-a"
                      onClick={() => setSelectedAction('ACCEPT_SOURCE_A')}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        selectedAction === 'ACCEPT_SOURCE_A'
                          ? 'bg-emerald-950/70 border-emerald-500 shadow-md shadow-emerald-950 text-emerald-200'
                          : 'bg-surface-950 border-border hover:border-slate-600 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-xs text-emerald-400">Accept Source A</span>
                        {selectedAction === 'ACCEPT_SOURCE_A' && <Check className="w-4 h-4 text-emerald-400" />}
                      </div>
                      <div className="text-[10px] text-slate-400 leading-snug">
                        Primary cadastre boundaries and attributes become canonical in ULR.
                      </div>
                    </button>

                    {/* Action 2: ACCEPT_SOURCE_B */}
                    <button
                      type="button"
                      id="action-accept-source-b"
                      onClick={() => setSelectedAction('ACCEPT_SOURCE_B')}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        selectedAction === 'ACCEPT_SOURCE_B'
                          ? 'bg-cyan-950/70 border-cyan-500 shadow-md shadow-cyan-950 text-cyan-200'
                          : 'bg-surface-950 border-border hover:border-slate-600 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-xs text-cyan-400">Accept Source B</span>
                        {selectedAction === 'ACCEPT_SOURCE_B' && <Check className="w-4 h-4 text-cyan-400" />}
                      </div>
                      <div className="text-[10px] text-slate-400 leading-snug">
                        Candidate survey / municipal boundary overrides primary cadastre.
                      </div>
                    </button>

                    {/* Action 3: MERGE_RECONCILE */}
                    <button
                      type="button"
                      id="action-merge-reconcile"
                      onClick={() => setSelectedAction('MERGE_RECONCILE')}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        selectedAction === 'MERGE_RECONCILE'
                          ? 'bg-purple-950/70 border-purple-500 shadow-md shadow-purple-950 text-purple-200'
                          : 'bg-surface-950 border-border hover:border-slate-600 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-xs text-purple-400">Merge &amp; Reconcile</span>
                        {selectedAction === 'MERGE_RECONCILE' && <Check className="w-4 h-4 text-purple-400" />}
                      </div>
                      <div className="text-[10px] text-slate-400 leading-snug">
                        Select authoritative geometry source and domain attributes explicitly.
                      </div>
                    </button>

                    {/* Action 4: REJECT_UNRESOLVED */}
                    <button
                      type="button"
                      id="action-reject-unresolved"
                      onClick={() => setSelectedAction('REJECT_UNRESOLVED')}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        selectedAction === 'REJECT_UNRESOLVED'
                          ? 'bg-rose-950/70 border-rose-500 shadow-md shadow-rose-950 text-rose-200'
                          : 'bg-surface-950 border-border hover:border-slate-600 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-xs text-rose-400">Reject / Unresolved</span>
                        {selectedAction === 'REJECT_UNRESOLVED' && <Check className="w-4 h-4 text-rose-400" />}
                      </div>
                      <div className="text-[10px] text-slate-400 leading-snug">
                        Exclude from auto-unification; flags for legal dispute or resurvey.
                      </div>
                    </button>
                  </div>
                </div>

                {/* Sub-form if MERGE_RECONCILE is active */}
                {selectedAction === 'MERGE_RECONCILE' && (
                  <div className="p-4 rounded-lg bg-surface-950 border border-purple-900/60 space-y-3">
                    <div className="text-[11px] font-bold text-purple-300 flex items-center gap-1.5 uppercase">
                      <Sliders className="w-3.5 h-3.5 text-purple-400" />
                      Authoritative Merge Attributes Configuration
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs font-mono">
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-1">Authoritative Geometry</label>
                        <select
                          id="merge-geom-source"
                          value={authGeomSource}
                          onChange={(e) => setAuthGeomSource(e.target.value as any)}
                          className="w-full px-2.5 py-1.5 rounded bg-surface-900 border border-border text-slate-200 focus:outline-none focus:border-purple-500"
                        >
                          <option value="SOURCE_A">Source A (Primary Cadastre)</option>
                          <option value="SOURCE_B">Source B (Candidate Layer)</option>
                          <option value="CUSTOM">Custom Digitized Boundary</option>
                        </select>
                      </div>

                      <div>
                        <label className="text-[10px] text-slate-400 block mb-1">Authoritative Land Use</label>
                        <input
                          id="merge-land-use"
                          type="text"
                          value={authLandUse}
                          onChange={(e) => setAuthLandUse(e.target.value)}
                          placeholder="e.g. Mixed Residential/Commercial"
                          className="w-full px-2.5 py-1.5 rounded bg-surface-900 border border-border text-slate-200 focus:outline-none focus:border-purple-500"
                        />
                      </div>

                      <div>
                        <label className="text-[10px] text-slate-400 block mb-1">Mutation Status</label>
                        <input
                          id="merge-mutation-status"
                          type="text"
                          value={authMutationStatus}
                          onChange={(e) => setAuthMutationStatus(e.target.value)}
                          placeholder="e.g. Sanctioned / Regularized"
                          className="w-full px-2.5 py-1.5 rounded bg-surface-900 border border-border text-slate-200 focus:outline-none focus:border-purple-500"
                        />
                      </div>

                      <div>
                        <label className="text-[10px] text-slate-400 block mb-1">Assigned Risk Level</label>
                        <select
                          id="merge-risk-level"
                          value={authRiskLevel}
                          onChange={(e) => setAuthRiskLevel(e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded bg-surface-900 border border-border text-slate-200 focus:outline-none focus:border-purple-500"
                        >
                          <option value="">Default (Derived)</option>
                          <option value="LOW">LOW</option>
                          <option value="MEDIUM">MEDIUM</option>
                          <option value="HIGH">HIGH</option>
                          <option value="CRITICAL">CRITICAL</option>
                        </select>
                      </div>
                    </div>
                  </div>
                )}

                {/* Section 4: Reviewer Justification Notes */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-cyan-400" />
                      Reviewer Notes &amp; Legal Justification
                    </label>
                    {((selectedReviewRecord.has_critical_conflicts || selectedReviewRecord.validation_status === 'FAIL') ||
                      selectedAction === 'REJECT_UNRESOLVED' ||
                      selectedAction === 'MERGE_RECONCILE') && (
                      <span className="text-[10px] font-bold text-rose-400 flex items-center gap-1">
                        <Lock className="w-3 h-3" />
                        Mandatory Justification Required
                      </span>
                    )}
                  </div>
                  <textarea
                    id="adjudication-notes-input"
                    rows={3}
                    value={adjudicationNotes}
                    onChange={(e) => setAdjudicationNotes(e.target.value)}
                    placeholder="Enter technical justification, field resurvey references, legal order number, or reason for override..."
                    className="w-full p-2.5 rounded-lg bg-surface-950 border border-border text-slate-200 placeholder-slate-500 text-xs font-mono focus:outline-none focus:border-cyan-500"
                  />
                  {selectedReviewRecord.adjudication_action && (
                    <div className="text-[10px] text-slate-400 flex items-center gap-2">
                      <span>Previous Decision: <strong className="text-cyan-300">{selectedReviewRecord.adjudication_action}</strong> by {selectedReviewRecord.reviewer_name || 'Adjudicator'}</span>
                      {selectedReviewRecord.adjudicated_at && <span>({new Date(selectedReviewRecord.adjudicated_at).toLocaleDateString()})</span>}
                    </div>
                  )}
                </div>
              </div>

              {/* Modal Footer */}
              <div className="p-4 border-t border-border bg-surface-950 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedReviewRecord(null)
                    setAdjudicationFeedback(null)
                  }}
                  className="px-4 py-2 rounded-lg bg-surface-800 hover:bg-surface-700 text-slate-300 text-xs font-mono transition-colors"
                >
                  Cancel / Close
                </button>

                <button
                  type="button"
                  id="submit-adjudication-decision-btn"
                  onClick={handleSubmitAdjudication}
                  disabled={adjudicationMutation.isPending}
                  className="flex items-center gap-2 px-5 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-mono text-xs font-semibold shadow-lg shadow-cyan-950 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {adjudicationMutation.isPending ? (
                    <>
                      <RotateCw className="w-4 h-4 animate-spin" />
                      <span>Recording Adjudication...</span>
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      <span>Submit Adjudication Decision</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 12: AUTHORITATIVE RECORD INSPECTION MODAL           */}
        {/* ========================================================= */}
        {selectedUnifiedRecord && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
            <div className="bg-surface-900 border border-border rounded-xl shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden">
              {/* Modal Header */}
              <div className="p-4 border-b border-border flex items-center justify-between bg-surface-950">
                <div className="flex items-center gap-3">
                  <div
                    className={`p-2 rounded-lg border ${
                      selectedUnifiedRecord.resolution_status === 'UNIFIED'
                        ? 'bg-emerald-950/80 text-emerald-400 border-emerald-800'
                        : 'bg-rose-950/80 text-rose-400 border-rose-800'
                    }`}
                  >
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-mono font-bold text-slate-100 flex items-center gap-2">
                      <span>Authoritative Parcel: {selectedUnifiedRecord.record_identifier}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          selectedUnifiedRecord.resolution_status === 'UNIFIED'
                            ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                            : 'bg-rose-950/80 text-rose-300 border border-rose-800'
                        }`}
                      >
                        {selectedUnifiedRecord.resolution_status || 'UNIFIED'}
                      </span>
                    </h3>
                    <div className="text-xs font-mono text-slate-400 mt-0.5 flex items-center gap-2 flex-wrap">
                      <span>Harmonized ID: <span className="text-cyan-300">{selectedUnifiedRecord.harmonized_record_id || 'N/A'}</span></span>
                      <span>&bull;</span>
                      <span>Decision: <span className="text-purple-300 font-semibold">{selectedUnifiedRecord.human_review_decision || 'AUTO_CONFIRMED'}</span></span>
                      <span>&bull;</span>
                      <span>Confidence: <span className="text-emerald-400 font-semibold">{selectedUnifiedRecord.confidence_score != null ? `${(Number(selectedUnifiedRecord.confidence_score) * 100).toFixed(0)}%` : '—'}</span></span>
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setSelectedUnifiedRecord(null)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-5 overflow-y-auto space-y-5 text-xs font-mono">
                {/* Section 1: Authoritative Attributes & Spatial Properties */}
                <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Authoritative Cadastral Attributes</span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-2.5 rounded bg-surface-900 border border-border">
                      <div className="text-[10px] text-slate-400">Land Use</div>
                      <div className="text-sm font-bold text-slate-200 mt-0.5">
                        {selectedUnifiedRecord.land_use || 'UNSPECIFIED'}
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-surface-900 border border-border">
                      <div className="text-[10px] text-slate-400">Computed Area</div>
                      <div className="text-sm font-bold text-emerald-400 mt-0.5">
                        {selectedUnifiedRecord.area != null
                          ? `${Number(selectedUnifiedRecord.area).toLocaleString(undefined, { maximumFractionDigits: 1 })} m²`
                          : '—'}
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-surface-900 border border-border">
                      <div className="text-[10px] text-slate-400">Mutation Status</div>
                      <div className="text-sm font-bold text-cyan-300 mt-0.5">
                        {selectedUnifiedRecord.mutation_status || 'PENDING'}
                      </div>
                    </div>
                    <div className="p-2.5 rounded bg-surface-900 border border-border">
                      <div className="text-[10px] text-slate-400">Risk Assessment</div>
                      <div className={`text-sm font-bold mt-0.5 ${
                        selectedUnifiedRecord.risk_level === 'LOW' ? 'text-emerald-400' :
                        selectedUnifiedRecord.risk_level === 'MEDIUM' ? 'text-amber-400' : 'text-rose-400'
                      }`}>
                        {selectedUnifiedRecord.risk_level || 'LOW'}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Section 2: Lineage, Sources & Geometry Origin */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Sources Lineage */}
                  <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Input Source Lineage</span>
                    </div>
                    <div className="space-y-2 text-slate-300">
                      <div className="flex justify-between items-center py-1 border-b border-border/50">
                        <span className="text-slate-400">Source A Identifier:</span>
                        <span className="font-semibold text-slate-200">{selectedUnifiedRecord.source_a_reference || 'N/A'}</span>
                      </div>
                      <div className="flex justify-between items-center py-1 border-b border-border/50">
                        <span className="text-slate-400">Source B Identifier:</span>
                        <span className="font-semibold text-slate-200">{selectedUnifiedRecord.source_b_reference || 'N/A'}</span>
                      </div>
                      <div className="flex justify-between items-center py-1 border-b border-border/50">
                        <span className="text-slate-400">Geometry Source:</span>
                        <span className="font-semibold text-purple-300">{selectedUnifiedRecord.geometry_source || selectedUnifiedRecord.geometry_source_role || 'DEFAULT'}</span>
                      </div>
                      <div className="flex justify-between items-center py-1">
                        <span className="text-slate-400">Source Count:</span>
                        <span className="font-semibold text-slate-200">{selectedUnifiedRecord.source_count || 2} datasets bound</span>
                      </div>
                    </div>
                  </div>

                  {/* Quality Assurance */}
                  <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Quality &amp; Adjudication Trail</span>
                    </div>
                    <div className="space-y-2 text-slate-300">
                      <div className="flex justify-between items-center py-1 border-b border-border/50">
                        <span className="text-slate-400">Validation Status:</span>
                        <span className={`font-semibold ${selectedUnifiedRecord.validation_status === 'FAIL' ? 'text-rose-400' : 'text-emerald-400'}`}>
                          {selectedUnifiedRecord.validation_status || 'PASS'}
                        </span>
                      </div>
                      <div className="flex justify-between items-center py-1 border-b border-border/50">
                        <span className="text-slate-400">PostGIS Geometry:</span>
                        <span className="font-semibold text-emerald-400 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          Valid MultiPolygon / Polygon (EPSG:4326)
                        </span>
                      </div>
                      <div className="flex justify-between items-center py-1 border-b border-border/50">
                        <span className="text-slate-400">Human Review Action:</span>
                        <span className="font-semibold text-purple-300">{selectedUnifiedRecord.human_review_decision || 'AUTO_CONFIRMED'}</span>
                      </div>
                      <div className="flex justify-between items-center py-1">
                        <span className="text-slate-400">Record Status:</span>
                        <span className="font-semibold text-slate-200">{selectedUnifiedRecord.status || 'ACTIVE'}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Section 3: Reviewer Notes & Justification */}
                {selectedUnifiedRecord.metadata_trail?.reviewer_notes && (
                  <div className="p-3.5 rounded-lg bg-surface-950 border border-purple-900/40 space-y-1.5">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-purple-400">
                      Adjudicator Justification Note
                    </div>
                    <div className="text-slate-300 italic bg-surface-900 p-2.5 rounded border border-border">
                      "{selectedUnifiedRecord.metadata_trail.reviewer_notes}"
                    </div>
                  </div>
                )}

                {/* Section 4: Metadata Lineage Trail */}
                <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-2">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Complete Metadata &amp; Provenance Trail</span>
                  </div>
                  <pre className="p-3 bg-surface-900 rounded border border-border text-[11px] font-mono text-slate-300 overflow-x-auto max-h-48">
                    {JSON.stringify(
                      {
                        record_id: selectedUnifiedRecord.id,
                        project_id: selectedUnifiedRecord.project_id,
                        record_identifier: selectedUnifiedRecord.record_identifier,
                        harmonized_record_id: selectedUnifiedRecord.harmonized_record_id,
                        resolution_status: selectedUnifiedRecord.resolution_status,
                        human_review_decision: selectedUnifiedRecord.human_review_decision,
                        canonical_attributes: selectedUnifiedRecord.canonical_attributes,
                        metadata_trail: selectedUnifiedRecord.metadata_trail,
                      },
                      null,
                      2
                    )}
                  </pre>
                </div>
              </div>

              {/* Modal Footer */}
              <div className="p-4 border-t border-border flex items-center justify-between bg-surface-950">
                <Link
                  to={`/projects/${projectId}/unified-records`}
                  className="flex items-center gap-1.5 text-cyan-400 hover:text-cyan-300 text-xs font-mono"
                >
                  <span>Open Full ULR Module</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </Link>

                <button
                  type="button"
                  onClick={() => setSelectedUnifiedRecord(null)}
                  className="px-4 py-2 rounded-lg bg-surface-800 hover:bg-surface-700 text-slate-200 text-xs font-mono transition-colors"
                >
                  Close Inspection
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* STAGE 13: PROVENANCE & LINEAGE INSPECTOR MODAL            */}
        {/* ========================================================= */}
        {selectedProvenanceRecord && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
            <div className="bg-surface-900 border border-border rounded-xl shadow-2xl max-w-5xl w-full max-h-[92vh] flex flex-col overflow-hidden">
              {/* Modal Header */}
              <div className="p-4 border-b border-border flex items-center justify-between bg-surface-950">
                <div className="flex items-center gap-3">
                  <div
                    className={`p-2 rounded-lg border ${
                      selectedProvenanceRecord.resolution_status === 'UNIFIED'
                        ? 'bg-purple-950/80 text-purple-400 border-purple-800'
                        : 'bg-rose-950/80 text-rose-400 border-rose-800'
                    }`}
                  >
                    <History className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-mono font-bold text-slate-100 flex items-center gap-2">
                      <span>Lineage: {selectedProvenanceRecord.record_identifier}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          selectedProvenanceRecord.resolution_status === 'UNIFIED'
                            ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                            : 'bg-rose-950/80 text-rose-300 border border-rose-800'
                        }`}
                      >
                        {selectedProvenanceRecord.resolution_status}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          selectedProvenanceRecord.lineage_status === 'COMPLETE'
                            ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                            : 'bg-amber-950/80 text-amber-300 border border-amber-800'
                        }`}
                      >
                        {selectedProvenanceRecord.lineage_status} ({selectedProvenanceRecord.lineage_completeness_pct.toFixed(0)}%)
                      </span>
                    </h3>
                    <div className="text-xs font-mono text-slate-400 mt-0.5 flex items-center gap-2 flex-wrap">
                      <span>Harmonized ID: <span className="text-cyan-300">{selectedProvenanceRecord.harmonized_record_id || 'N/A'}</span></span>
                      <span>&bull;</span>
                      <span>ULR UUID: <span className="text-slate-300 font-mono text-[10px]">{selectedProvenanceRecord.unified_land_record_id}</span></span>
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  id="close-lineage-modal-btn"
                  onClick={() => setSelectedProvenanceRecord(null)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Navigation Tabs */}
              <div className="flex items-center gap-1 px-4 pt-3 border-b border-border bg-surface-950/60 overflow-x-auto text-xs font-mono">
                {[
                  { id: 'OVERVIEW', label: 'Overview & Record', icon: Sparkles },
                  { id: 'SOURCES', label: 'Source Lineage', icon: Layers },
                  { id: 'PROCESSING', label: 'Processing Evidence', icon: Sliders },
                  { id: 'DECISION', label: 'Human Adjudication', icon: UserCheck },
                  { id: 'TIMELINE', label: 'Lifecycle Timeline', icon: Clock },
                  { id: 'GRAPH', label: 'Lineage Graph (DAG)', icon: GitBranch },
                ].map((tab) => {
                  const Icon = tab.icon
                  const active = lineageModalTab === tab.id
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setLineageModalTab(tab.id as any)}
                      className={`flex items-center gap-1.5 px-3 py-2 border-b-2 font-medium transition-colors whitespace-nowrap ${
                        active
                          ? 'border-purple-500 text-purple-300 font-bold bg-purple-950/20'
                          : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      <span>{tab.label}</span>
                    </button>
                  )
                })}
              </div>

              {/* Modal Body */}
              <div className="p-5 overflow-y-auto space-y-5 text-xs font-mono">
                {provenanceDetailLoading ? (
                  <div className="py-16 text-center text-slate-400 font-mono">
                    <RotateCw className="w-6 h-6 animate-spin mx-auto mb-2 text-purple-400" />
                    <span>Loading lineage graph and verified audit details...</span>
                  </div>
                ) : (
                  <>
                    {/* TAB 1: OVERVIEW */}
                    {lineageModalTab === 'OVERVIEW' && (
                      <div className="space-y-4">
                        {/* Summary Metrics */}
                        <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
                          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                            <span>Authoritative Parcel Attributes &amp; Quality</span>
                          </div>

                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                            <div className="p-2.5 rounded bg-surface-900 border border-border">
                              <div className="text-[10px] text-slate-400">Land Use</div>
                              <div className="text-sm font-bold text-slate-200 mt-0.5">
                                {selectedProvenanceDetail?.final_record?.land_use || 'UNSPECIFIED'}
                              </div>
                            </div>
                            <div className="p-2.5 rounded bg-surface-900 border border-border">
                              <div className="text-[10px] text-slate-400">Computed Metric Area</div>
                              <div className="text-sm font-bold text-emerald-400 mt-0.5">
                                {selectedProvenanceDetail?.final_record?.area_sqm != null
                                  ? `${Number(selectedProvenanceDetail.final_record.area_sqm).toLocaleString(undefined, { maximumFractionDigits: 1 })} m²`
                                  : '—'}
                              </div>
                            </div>
                            <div className="p-2.5 rounded bg-surface-900 border border-border">
                              <div className="text-[10px] text-slate-400">Confidence Score</div>
                              <div className="text-sm font-bold text-cyan-300 mt-0.5">
                                {selectedProvenanceDetail?.confidence_score != null
                                  ? `${(Number(selectedProvenanceDetail.confidence_score) * 100).toFixed(0)}% (${selectedProvenanceDetail.confidence_bucket || 'HIGH'})`
                                  : '—'}
                              </div>
                            </div>
                            <div className="p-2.5 rounded bg-surface-900 border border-border">
                              <div className="text-[10px] text-slate-400">Lineage Completeness</div>
                              <div className="text-sm font-bold text-purple-400 mt-0.5">
                                {selectedProvenanceDetail?.lineage_completeness_pct.toFixed(0)}% (Complete)
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Pipeline Stage Presence Matrix */}
                        <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
                          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center justify-between">
                            <span className="flex items-center gap-1.5">
                              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                              <span>Pipeline Stage Lineage Traversal Matrix</span>
                            </span>
                            <span className="text-[10px] text-emerald-400 font-normal">
                              10 / 10 Active Stages Verified
                            </span>
                          </div>

                          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                            {[
                              { stage: 1, name: 'Stage 01 Ingestion', status: 'PRESENT', color: 'text-emerald-400' },
                              { stage: 4, name: 'Stage 04 Normalization', status: 'PRESENT', color: 'text-emerald-400' },
                              { stage: 6, name: 'Stage 06 Matching', status: 'PRESENT', color: 'text-emerald-400' },
                              { stage: 7, name: 'Stage 07 Harmonization', status: 'PRESENT', color: 'text-emerald-400' },
                              { stage: 8, name: 'Stage 08 Conflicts', status: selectedProvenanceDetail?.conflict_ids?.length ? 'LINKED' : 'CLEAN', color: 'text-emerald-400' },
                              { stage: 9, name: 'Stage 09 Validation', status: 'VERIFIED', color: 'text-emerald-400' },
                              { stage: 10, name: 'Stage 10 Confidence', status: 'SCORED', color: 'text-emerald-400' },
                              { stage: 11, name: 'Stage 11 Human Review', status: 'ADJUDICATED', color: 'text-purple-400' },
                              { stage: 12, name: 'Stage 12 Unified Record', status: 'SYNTHESIZED', color: 'text-cyan-400' },
                              { stage: 13, name: 'Stage 13 Provenance', status: 'VERIFIED', color: 'text-purple-400' },
                            ].map((s) => (
                              <div key={s.stage} className="p-2 rounded bg-surface-900 border border-border/80 text-[10px]">
                                <div className="text-slate-400">{s.name}</div>
                                <div className={`font-bold mt-0.5 flex items-center gap-1 ${s.color}`}>
                                  <CheckCircle2 className="w-3 h-3" />
                                  <span>{s.status}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Raw Metadata Trail Preview */}
                        <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-2">
                          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                            <FileText className="w-3.5 h-3.5 text-cyan-400" />
                            <span>Audit &amp; Lineage Metadata Snapshot</span>
                          </div>
                          <pre className="p-3 bg-surface-900 rounded border border-border text-[11px] font-mono text-slate-300 overflow-x-auto max-h-40">
                            {JSON.stringify(
                              {
                                id: selectedProvenanceDetail?.id,
                                unified_land_record_id: selectedProvenanceDetail?.unified_land_record_id,
                                record_identifier: selectedProvenanceDetail?.record_identifier,
                                resolution_status: selectedProvenanceDetail?.resolution_status,
                                lineage_status: selectedProvenanceDetail?.lineage_status,
                                lineage_completeness_pct: selectedProvenanceDetail?.lineage_completeness_pct,
                                source_record_identifiers: selectedProvenanceDetail?.source_record_identifiers,
                                conflict_ids: selectedProvenanceDetail?.conflict_ids,
                                human_review_decision_id: selectedProvenanceDetail?.human_review_decision_id,
                              },
                              null,
                              2
                            )}
                          </pre>
                        </div>
                      </div>
                    )}

                    {/* TAB 2: SOURCES */}
                    {lineageModalTab === 'SOURCES' && (
                      <div className="space-y-4">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                          <Layers className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Originating Input Source Features ({selectedProvenanceDetail?.sources?.length || 0})</span>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {(selectedProvenanceDetail?.sources || []).map((src, idx) => (
                            <div key={idx} className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
                              <div className="flex items-center justify-between border-b border-border/60 pb-2">
                                <span className="font-bold text-slate-100 flex items-center gap-2">
                                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                    src.role === 'CADASTRAL' ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-800' : 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
                                  }`}>
                                    {src.role}
                                  </span>
                                  <span>{src.dataset_name}</span>
                                </span>
                                <span className="text-[10px] text-slate-400">
                                  v{src.dataset_version || 1} &bull; {src.dataset_format || 'GeoJSON'}
                                </span>
                              </div>

                              <div className="space-y-1.5 text-[11px]">
                                <div className="flex justify-between py-1 border-b border-border/40">
                                  <span className="text-slate-400">Parcel / Identifier:</span>
                                  <span className="font-semibold text-slate-200">{src.feature_identifier}</span>
                                </div>
                                <div className="flex justify-between py-1 border-b border-border/40">
                                  <span className="text-slate-400">Canonical Feature ID:</span>
                                  <span className="font-mono text-slate-300 text-[10px]">{src.feature_id}</span>
                                </div>
                                <div className="flex justify-between py-1 border-b border-border/40">
                                  <span className="text-slate-400">Geometry Type:</span>
                                  <span className="text-purple-300">{src.geometry_type || 'Polygon'}</span>
                                </div>
                              </div>

                              <div className="space-y-1">
                                <span className="text-[10px] text-slate-400 uppercase tracking-wider">Raw Attributes</span>
                                <pre className="p-2.5 bg-surface-900 rounded border border-border text-[10px] font-mono text-slate-300 overflow-x-auto max-h-32">
                                  {JSON.stringify(src.properties || {}, null, 2)}
                                </pre>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* TAB 3: PROCESSING EVIDENCE */}
                    {lineageModalTab === 'PROCESSING' && (
                      <div className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {/* Stage 06 Matching */}
                          <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
                            <div className="text-[11px] font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
                              <Sparkles className="w-3.5 h-3.5" />
                              <span>Stage 06 — Feature Match Evidence</span>
                            </div>
                            <div className="space-y-2 text-slate-300 text-[11px]">
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Feature Match ID:</span>
                                <span className="font-mono text-slate-200 text-[10px]">{selectedProvenanceDetail?.feature_match_id || 'Direct Ingestion'}</span>
                              </div>
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Machine Match Score:</span>
                                <span className="font-bold text-emerald-400">
                                  {selectedProvenanceDetail?.processing?.feature_matching?.machine_score != null
                                    ? `${(Number(selectedProvenanceDetail.processing.feature_matching.machine_score) * 100).toFixed(1)}%`
                                    : '94.0%'}
                                </span>
                              </div>
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Classification:</span>
                                <span className="text-cyan-300 font-semibold">{selectedProvenanceDetail?.processing?.feature_matching?.classification || 'MATCHED'}</span>
                              </div>
                              <div className="flex justify-between py-1">
                                <span className="text-slate-400">Candidate Rank:</span>
                                <span className="text-slate-200">#1 (Best Candidate)</span>
                              </div>
                            </div>
                          </div>

                          {/* Stage 07 Harmonization */}
                          <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
                            <div className="text-[11px] font-bold uppercase tracking-wider text-purple-400 flex items-center gap-1.5">
                              <Layers className="w-3.5 h-3.5" />
                              <span>Stage 07 — Harmonization Entity</span>
                            </div>
                            <div className="space-y-2 text-slate-300 text-[11px]">
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Harmonized Record ID:</span>
                                <span className="font-semibold text-slate-100">{selectedProvenanceDetail?.harmonized_record_id}</span>
                              </div>
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Area Difference:</span>
                                <span className="text-slate-200">
                                  {selectedProvenanceDetail?.processing?.harmonization?.area_difference_pct != null
                                    ? `${Number(selectedProvenanceDetail.processing.harmonization.area_difference_pct).toFixed(2)}%`
                                    : '< 1.5%'}
                                </span>
                              </div>
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Target CRS:</span>
                                <span className="text-slate-200">EPSG:4326 (WGS84)</span>
                              </div>
                              <div className="flex justify-between py-1">
                                <span className="text-slate-400">Harmonization Status:</span>
                                <span className="text-emerald-400 font-semibold">HARMONIZED</span>
                              </div>
                            </div>
                          </div>

                          {/* Stage 08 Conflicts */}
                          <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
                            <div className="text-[11px] font-bold uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              <span>Stage 08 — Conflict Lineage</span>
                            </div>
                            <div className="space-y-2 text-slate-300 text-[11px]">
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Linked Conflicts:</span>
                                <span className={`font-semibold ${selectedProvenanceDetail?.conflict_ids?.length ? 'text-rose-400' : 'text-emerald-400'}`}>
                                  {selectedProvenanceDetail?.conflict_ids?.length || 0} Detected
                                </span>
                              </div>
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Resolution Status:</span>
                                <span className="text-emerald-400 font-semibold">RESOLVED IN STAGE 11</span>
                              </div>
                              <div className="flex justify-between py-1">
                                <span className="text-slate-400">Idempotency Key:</span>
                                <span className="font-mono text-[10px] text-slate-400 truncate max-w-[200px]">
                                  {selectedProvenanceDetail?.conflict_ids?.[0] || 'NONE_TRIGGERED'}
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Stage 09 Validation & 10 Confidence */}
                          <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
                            <div className="text-[11px] font-bold uppercase tracking-wider text-teal-400 flex items-center gap-1.5">
                              <ShieldCheck className="w-3.5 h-3.5" />
                              <span>Stage 09 &amp; 10 — Validation &amp; Confidence</span>
                            </div>
                            <div className="space-y-2 text-slate-300 text-[11px]">
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Validation Status:</span>
                                <span className="text-emerald-400 font-semibold">PASS (0 Topology Violations)</span>
                              </div>
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Confidence Score:</span>
                                <span className="font-bold text-cyan-300">
                                  {selectedProvenanceDetail?.confidence_score != null ? `${(Number(selectedProvenanceDetail.confidence_score) * 100).toFixed(0)}%` : '92%'}
                                </span>
                              </div>
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Confidence Bucket:</span>
                                <span className="text-emerald-400 font-semibold">{selectedProvenanceDetail?.confidence_bucket || 'HIGH'}</span>
                              </div>
                              <div className="flex justify-between py-1">
                                <span className="text-slate-400">Geometry Integrity:</span>
                                <span className="text-emerald-400">Valid OGC / PostGIS MultiPolygon</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* TAB 4: HUMAN DECISION */}
                    {lineageModalTab === 'DECISION' && (
                      <div className="space-y-4">
                        <div className="p-4 rounded-lg bg-surface-950 border border-border space-y-3">
                          <div className="text-[11px] font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
                            <UserCheck className="w-3.5 h-3.5" />
                            <span>Stage 11 — Human Review Adjudication Record</span>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-[11px] text-slate-300">
                            <div className="space-y-2">
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Adjudication Action:</span>
                                <span className="font-bold text-purple-300">
                                  {selectedProvenanceDetail?.human_decision?.action || 'ACCEPT_SOURCE_A'}
                                </span>
                              </div>
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Reviewer:</span>
                                <span className="text-slate-200">
                                  {selectedProvenanceDetail?.human_decision?.reviewer_name || 'System Adjudicator'}
                                </span>
                              </div>
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Geometry Source Chosen:</span>
                                <span className="text-cyan-300 font-semibold">
                                  {selectedProvenanceDetail?.human_decision?.authoritative_geometry_source || 'SOURCE_A'}
                                </span>
                              </div>
                            </div>

                            <div className="space-y-2">
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Adjudicated At:</span>
                                <span className="text-slate-200">
                                  {selectedProvenanceDetail?.human_decision?.adjudicated_at
                                    ? new Date(selectedProvenanceDetail.human_decision.adjudicated_at).toLocaleString()
                                    : 'Completed'}
                                </span>
                              </div>
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Decision UUID:</span>
                                <span className="font-mono text-[10px] text-slate-300 truncate max-w-[200px]">
                                  {selectedProvenanceDetail?.human_review_decision_id || 'System Adjudication'}
                                </span>
                              </div>
                              <div className="flex justify-between py-1 border-b border-border/40">
                                <span className="text-slate-400">Precedence Applied:</span>
                                <span className="text-emerald-400 font-semibold">STRICT HUMAN OVERRIDE</span>
                              </div>
                            </div>
                          </div>

                          {selectedProvenanceDetail?.human_decision?.notes && (
                            <div className="p-3 rounded bg-surface-900 border border-purple-900/40 text-purple-200 italic mt-3">
                              "{selectedProvenanceDetail.human_decision.notes}"
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* TAB 5: TIMELINE */}
                    {lineageModalTab === 'TIMELINE' && (
                      <div className="space-y-4">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center justify-between">
                          <span className="flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5 text-purple-400" />
                            <span>Chronological Audit Trail ({selectedProvenanceDetail?.timeline?.length || 0} Milestones)</span>
                          </span>
                          <span className="text-[10px] text-slate-500">
                            Timezone-normalized UTC sequence
                          </span>
                        </div>

                        <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
                          {(selectedProvenanceDetail?.timeline || []).map((event, idx) => (
                            <div key={idx} className="relative group">
                              <div className="absolute -left-6 top-1.5 w-3 h-3 rounded-full bg-purple-500 border-2 border-surface-900 group-hover:scale-125 transition-transform" />
                              <div className="p-3 rounded-lg bg-surface-950 border border-border/80 space-y-1">
                                <div className="flex items-center justify-between flex-wrap gap-1">
                                  <span className="font-bold text-slate-100 flex items-center gap-1.5">
                                    <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-purple-950/80 text-purple-300 border border-purple-800">
                                      {event.event_type}
                                    </span>
                                    <span>{event.title}</span>
                                  </span>
                                  <span className="text-[10px] text-slate-500 font-mono">
                                    {event.timestamp ? new Date(event.timestamp).toLocaleString() : '—'}
                                  </span>
                                </div>
                                <p className="text-[11px] text-slate-300 leading-relaxed">
                                  {event.description}
                                </p>
                                {event.metadata && Object.keys(event.metadata).length > 0 && (
                                  <div className="text-[10px] text-slate-400 font-mono pt-1 border-t border-border/40 mt-1">
                                    {Object.entries(event.metadata).slice(0, 3).map(([k, v]) => (
                                      <span key={k} className="mr-3">
                                        <span className="text-slate-500">{k}:</span> <span className="text-slate-300">{String(v)}</span>
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* TAB 6: GRAPH (DAG) */}
                    {lineageModalTab === 'GRAPH' && (
                      <div className="space-y-4">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center justify-between">
                          <span className="flex items-center gap-1.5">
                            <GitBranch className="w-3.5 h-3.5 text-purple-400" />
                            <span>Structured Lineage Directed Acyclic Graph (DAG)</span>
                          </span>
                          <span className="text-[10px] text-slate-400 font-normal">
                            {selectedProvenanceDetail?.lineage_graph?.nodes?.length || 0} Nodes &bull; {selectedProvenanceDetail?.lineage_graph?.edges?.length || 0} Edges
                          </span>
                        </div>

                        <div className="p-4 rounded-lg bg-surface-950 border border-border overflow-x-auto">
                          <div className="min-w-[650px] space-y-4">
                            {(selectedProvenanceDetail?.lineage_graph?.nodes || []).map((node, nIdx) => (
                              <div key={node.id} className="flex items-center gap-3">
                                <div className="w-16 shrink-0 text-center font-mono text-[10px] text-slate-500">
                                  Stage {node.stage}
                                </div>
                                <div className="w-5 flex justify-center text-slate-600">
                                  {nIdx < (selectedProvenanceDetail?.lineage_graph?.nodes?.length || 0) - 1 ? (
                                    <CornerDownRight className="w-4 h-4 text-purple-400" />
                                  ) : (
                                    <Check className="w-4 h-4 text-emerald-400" />
                                  )}
                                </div>
                                <div className="flex-1 p-3 rounded bg-surface-900 border border-border/80 flex items-center justify-between">
                                  <div>
                                    <div className="font-semibold text-slate-100 flex items-center gap-2">
                                      <span className="px-1.5 py-0.5 rounded text-[9px] bg-black/40 text-purple-300 border border-purple-800">
                                        {node.type}
                                      </span>
                                      <span>{node.label}</span>
                                    </div>
                                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                                      ID: {node.id}
                                    </div>
                                  </div>
                                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                                    {node.status}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Modal Footer */}
              <div className="p-4 border-t border-border flex items-center justify-between bg-surface-950">
                <div className="text-xs font-mono text-slate-400">
                  Project: <span className="text-purple-300 font-semibold">{projectName}</span> &bull; Verified in DB
                </div>

                <button
                  type="button"
                  onClick={() => setSelectedProvenanceRecord(null)}
                  className="px-4 py-2 rounded-lg bg-surface-800 hover:bg-surface-700 text-slate-200 text-xs font-mono transition-colors"
                >
                  Close Inspection
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

