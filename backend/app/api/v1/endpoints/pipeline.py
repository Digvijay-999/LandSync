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
)
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
