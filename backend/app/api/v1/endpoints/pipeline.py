import uuid
from typing import Annotated
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.schemas.pipeline import (
    PipelineStatusResponse,
    CandidateGenerationRequest,
    CandidateGenerationResponse,
    FeatureMatchingRunRequest,
    FeatureMatchingRunResponse,
    HarmonizationRunRequest,
    HarmonizationRunResponse,
    ConflictDetectionRunRequest,
    ConflictDetectionRunResponse,
    ValidationRunRequest,
    ValidationRunResponse,
    ConfidenceScoringRunRequest,
    ConfidenceScoringRunResponse,
)
from app.schemas.adjudication import Stage11ExecutionResponse
from app.schemas.unified import Stage12ExecutionResponse, Stage12StatusResponse
from app.schemas.provenance import Stage13ExecutionResponse, Stage13StatusResponse
from app.schemas.export import Stage14ExecutionResponse, Stage14StatusResponse
from app.services.pipeline.service import PipelineService

router = APIRouter()


@router.get(
    "/projects/{project_id}/pipeline/status",
    response_model=PipelineStatusResponse,
    summary="Get Pipeline Workflow Status",
    description="Returns the execution status, prerequisite readiness, and result summaries for all 14 pipeline stages.",
)
async def get_pipeline_status(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> PipelineStatusResponse:
    try:
        return await PipelineService.get_pipeline_status(db=db, project_id=project_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pipeline status: {str(exc)}",
        )


@router.post(
    "/projects/{project_id}/pipeline/candidate-generation/run",
    response_model=CandidateGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Run Stage 05: Spatial Candidate Generation",
    description="Executes PostGIS spatial indexing, intersection, containment, and distance analysis across ingested datasets.",
)
async def run_candidate_generation(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    data: CandidateGenerationRequest = CandidateGenerationRequest(),
) -> CandidateGenerationResponse:
    try:
        return await PipelineService.run_candidate_generation(
            db=db, project_id=project_id, req=data
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Candidate generation failed: {str(exc)}",
        )


@router.post(
    "/projects/{project_id}/pipeline/feature-matching/run",
    response_model=FeatureMatchingRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run Stage 06: Feature Matching",
    description="Consumes candidate parcel pairs and computes multi-signal matching scores (spatial IoU, Hausdorff, centroid, attributes).",
)
async def run_feature_matching(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    data: FeatureMatchingRunRequest = FeatureMatchingRunRequest(),
) -> FeatureMatchingRunResponse:
    try:
        return await PipelineService.run_feature_matching(
            db=db, project_id=project_id, req=data
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Feature matching failed: {str(exc)}",
        )


@router.post(
    "/projects/{project_id}/pipeline/harmonization/run",
    response_model=HarmonizationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run Stage 07: Attribute/Geometry Harmonization",
    description="Resolves authoritative geometry and reconciles attributes using semantic domain hierarchy.",
)
async def run_harmonization(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    data: HarmonizationRunRequest = HarmonizationRunRequest(),
) -> HarmonizationRunResponse:
    try:
        return await PipelineService.run_harmonization(
            db=db, project_id=project_id, req=data
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Harmonization failed: {str(exc)}",
        )


@router.post(
    "/projects/{project_id}/pipeline/stage-08/execute",
    response_model=ConflictDetectionRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Stage 08: Conflict Detection",
    description="Consumes Stage 07 harmonized records and candidate pairs, detects conflicts across area, land-use, mutation, risk, and geometry, and persists conflict records idempotently.",
)
async def execute_stage_08(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    data: ConflictDetectionRunRequest = ConflictDetectionRunRequest(),
) -> ConflictDetectionRunResponse:
    try:
        return await PipelineService.run_conflict_detection(
            db=db, project_id=project_id, req=data
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conflict detection failed: {str(exc)}",
        )


@router.post(
    "/projects/{project_id}/pipeline/conflict-detection/run",
    response_model=ConflictDetectionRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run Stage 08: Conflict Detection",
    description="Alias endpoint for executing Stage 08 Conflict Detection.",
)
async def run_conflict_detection(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    data: ConflictDetectionRunRequest = ConflictDetectionRunRequest(),
) -> ConflictDetectionRunResponse:
    return await execute_stage_08(project_id=project_id, db=db, data=data)


@router.post(
    "/projects/{project_id}/pipeline/stage-09/execute",
    response_model=ValidationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Stage 09: Validation",
    description="Verifies candidate records using PostGIS geometry checks, topological integrity, area tolerance thresholds, semantic business rules, and Stage 08 conflict results.",
)
async def execute_stage_09(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    data: ValidationRunRequest = ValidationRunRequest(),
) -> ValidationRunResponse:
    try:
        return await PipelineService.run_validation(
            db=db, project_id=project_id, req=data
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation stage failed: {str(exc)}",
        )


@router.post(
    "/projects/{project_id}/pipeline/validation/run",
    response_model=ValidationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run Stage 09: Validation",
    description="Alias endpoint for executing Stage 09 Validation.",
)
async def run_validation(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    data: ValidationRunRequest = ValidationRunRequest(),
) -> ValidationRunResponse:
    return await execute_stage_09(project_id=project_id, db=db, data=data)


@router.post(
    "/projects/{project_id}/pipeline/stage-10/execute",
    response_model=ConfidenceScoringRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Pipeline Stage 10: Confidence Scoring",
    description="Calculates transparent multi-component confidence scores (spatial, geometry, attribute, temporal) with explainable signal breakdown, bucket assignment, and validation/conflict constraint enforcement.",
)
async def execute_stage_10(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    data: ConfidenceScoringRunRequest = ConfidenceScoringRunRequest(),
) -> ConfidenceScoringRunResponse:
    try:
        return await PipelineService.run_confidence_scoring(
            db=db, project_id=project_id, req=data
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Confidence scoring stage failed: {str(exc)}",
        )


@router.post(
    "/projects/{project_id}/pipeline/confidence-scoring/run",
    response_model=ConfidenceScoringRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run Stage 10: Confidence Scoring",
    description="Alias endpoint for executing Stage 10 Confidence Scoring.",
)
async def run_confidence_scoring(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    data: ConfidenceScoringRunRequest = ConfidenceScoringRunRequest(),
) -> ConfidenceScoringRunResponse:
    return await execute_stage_10(project_id=project_id, db=db, data=data)


@router.post(
    "/projects/{project_id}/pipeline/stage-11/execute",
    response_model=Stage11ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute / Finalize Stage 11: Human Review",
    description="Evaluates completion of the human review queue. Transitions Stage 11 to completed if all mandatory records are adjudicated.",
)
async def execute_stage_11(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage11ExecutionResponse:
    try:
        from app.services.adjudication.service import AdjudicationService
        return await AdjudicationService.finalize_stage_11(db=db, project_id=project_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Human review stage finalization failed: {str(exc)}",
        )


@router.post(
    "/projects/{project_id}/pipeline/stage-12/execute",
    response_model=Stage12ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Pipeline Stage 12: Unified Record",
    description="Synthesizes authoritative master land records by combining harmonized, validated, and human-adjudicated data.",
)
async def execute_stage_12(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage12ExecutionResponse:
    try:
        from app.services.unified.service import UnifiedRecordService
        return await UnifiedRecordService.synthesize_stage_12(db=db, project_id=project_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unified record synthesis failed: {str(exc)}",
        )


@router.post(
    "/projects/{project_id}/pipeline/stages/12/execute",
    response_model=Stage12ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Pipeline Stage 12: Unified Record (Alias)",
    description="Alias endpoint for executing Stage 12 Unified Record synthesis.",
)
async def execute_stage_12_alias(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage12ExecutionResponse:
    return await execute_stage_12(project_id=project_id, db=db)


@router.get(
    "/projects/{project_id}/pipeline/stage-12/status",
    response_model=Stage12StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Pipeline Stage 12: Unified Record Status",
    description="Returns live execution status, metrics, and progress for Stage 12 Unified Record.",
)
async def get_stage_12_status(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage12StatusResponse:
    try:
        from app.services.unified.service import UnifiedRecordService
        return await UnifiedRecordService.get_stage12_status(db=db, project_id=project_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Stage 12 status: {str(exc)}",
        )


@router.get(
    "/projects/{project_id}/pipeline/stages/12/status",
    response_model=Stage12StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Pipeline Stage 12: Unified Record Status (Alias)",
    description="Alias endpoint for getting Stage 12 Unified Record status.",
)
async def get_stage_12_status_alias(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage12StatusResponse:
    return await get_stage_12_status(project_id=project_id, db=db)


# =============================================================================
# STAGE 13 — PROVENANCE ENDPOINTS
# =============================================================================

@router.post(
    "/projects/{project_id}/pipeline/stage-13/execute",
    response_model=Stage13ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Pipeline Stage 13: Provenance",
    description="Generates persistent, deterministic provenance records and audit timelines connecting Stage 12 unified records back through all upstream stages.",
)
async def execute_stage_13(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage13ExecutionResponse:
    try:
        from app.services.provenance.service import ProvenanceService
        return await ProvenanceService.execute_stage_13(db=db, project_id=project_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Provenance execution failed: {str(exc)}",
        )


@router.post(
    "/projects/{project_id}/pipeline/stages/13/execute",
    response_model=Stage13ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Pipeline Stage 13: Provenance (Alias)",
    description="Alias endpoint for executing Stage 13 Provenance.",
)
async def execute_stage_13_alias(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage13ExecutionResponse:
    return await execute_stage_13(project_id=project_id, db=db)


@router.get(
    "/projects/{project_id}/pipeline/stage-13/status",
    response_model=Stage13StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Pipeline Stage 13: Provenance Status",
    description="Returns live execution status, metrics, completeness stats, and audit counts for Stage 13 Provenance.",
)
async def get_stage_13_status(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage13StatusResponse:
    try:
        from app.services.provenance.service import ProvenanceService
        return await ProvenanceService.get_stage13_status(db=db, project_id=project_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Stage 13 status: {str(exc)}",
        )


@router.get(
    "/projects/{project_id}/pipeline/stages/13/status",
    response_model=Stage13StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Pipeline Stage 13: Provenance Status (Alias)",
    description="Alias endpoint for getting Stage 13 Provenance status.",
)
async def get_stage_13_status_alias(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage13StatusResponse:
    return await get_stage_13_status(project_id=project_id, db=db)


# =============================================================================
# STAGE 14 — EXPORT & DELIVERABLES ENDPOINTS
# =============================================================================

@router.post(
    "/projects/{project_id}/pipeline/stage-14/execute",
    response_model=Stage14ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Pipeline Stage 14: Export",
    description="Generates authoritative deliverables (GeoJSON, GeoPackage, CSV) and defensible lineage manifests from verified pipeline data.",
)
async def execute_stage_14(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage14ExecutionResponse:
    try:
        from app.services.export.service import ExportService
        return await ExportService.execute_stage_14(db=db, project_id=project_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export execution failed: {str(exc)}",
        )


@router.post(
    "/projects/{project_id}/pipeline/stages/14/execute",
    response_model=Stage14ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Pipeline Stage 14: Export (Alias)",
    description="Alias endpoint for executing Stage 14 Export.",
)
async def execute_stage_14_alias(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage14ExecutionResponse:
    return await execute_stage_14(project_id=project_id, db=db)


@router.get(
    "/projects/{project_id}/pipeline/stage-14/status",
    response_model=Stage14StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Pipeline Stage 14: Export Status",
    description="Returns live execution status, metrics, available formats, and recent deliverable exports for Stage 14.",
)
async def get_stage_14_status(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage14StatusResponse:
    try:
        from app.services.export.service import ExportService
        return await ExportService.get_stage14_status(db=db, project_id=project_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Stage 14 status: {str(exc)}",
        )


@router.get(
    "/projects/{project_id}/pipeline/stages/14/status",
    response_model=Stage14StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Pipeline Stage 14: Export Status (Alias)",
    description="Alias endpoint for getting Stage 14 Export status.",
)
async def get_stage_14_status_alias(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> Stage14StatusResponse:
    return await get_stage_14_status(project_id=project_id, db=db)





