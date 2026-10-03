import uuid
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.services.confidence.service import ConfidenceScoringService
from app.schemas.confidence import (
    ConfidenceRecordItem,
    ConfidenceSummaryResponse,
    ConfidenceResultListResponse,
)

router = APIRouter()


@router.get(
    "/projects/{project_id}/confidence-results",
    response_model=ConfidenceResultListResponse,
    status_code=status.HTTP_200_OK,
    summary="List paginated confidence scoring results for a project",
    description="Returns Stage 10 confidence records with explainable multi-component signal breakdowns (spatial, geometry, attribute, temporal), weights, contributions, and reasoning.",
)
async def list_confidence_results(
    project_id: uuid.UUID,
    bucket: Optional[str] = Query(None, description="Filter by confidence bucket (HIGH, MEDIUM, LOW, AMBIGUOUS)"),
    review_status: Optional[str] = Query(None, description="Filter by review status (AUTO_CONFIRMED, PENDING, FLAGGED, REQUIRES_REVIEW)"),
    search: Optional[str] = Query(None, description="Filter by identifier or parcel ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = SessionDep,
) -> ConfidenceResultListResponse:
    try:
        return await ConfidenceScoringService.list_confidence_results(
            db=db,
            project_id=project_id,
            bucket=bucket,
            review_status=review_status,
            search=search,
            skip=skip,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch confidence results: {str(e)}",
        )


@router.get(
    "/projects/{project_id}/confidence-summary",
    response_model=ConfidenceSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project confidence scoring summary statistics",
    description="Returns aggregate counts of HIGH, MEDIUM, LOW, AMBIGUOUS, review required, auto-confirmed, and average confidence.",
)
async def get_confidence_summary(
    project_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> ConfidenceSummaryResponse:
    try:
        return await ConfidenceScoringService.get_confidence_summary(db=db, project_id=project_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute confidence summary: {str(e)}",
        )


@router.get(
    "/confidence-results/{record_id}",
    response_model=ConfidenceRecordItem,
    status_code=status.HTTP_200_OK,
    summary="Get individual confidence scoring detail",
    description="Returns full explainable confidence signal breakdown for a feature record, including weights, raw component scores, weighted contributions, validation/conflict impacts, and reasoning.",
)
async def get_confidence_result_detail(
    record_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> Any:
    result = await ConfidenceScoringService.get_confidence_result_detail(db=db, record_id=record_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Confidence result record with ID '{record_id}' not found.",
        )
    return result
