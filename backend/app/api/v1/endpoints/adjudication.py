import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.services.adjudication.service import AdjudicationService
from app.schemas.adjudication import (
    ReviewQueueItem,
    ReviewQueueSummaryResponse,
    ReviewQueueListResponse,
    AdjudicationActionRequest,
    AdjudicationActionResponse,
    Stage11ExecutionResponse,
)

router = APIRouter()


@router.get(
    "/projects/{project_id}/review-summary",
    response_model=ReviewQueueSummaryResponse,
    summary="Get Human Review Summary",
    description="Returns aggregate summary of Stage 11 review queue, resolution progress, and stage status.",
)
async def get_review_summary(
    project_id: Annotated[uuid.UUID, Path(..., description="Project workspace identifier")],
    db: Annotated[AsyncSession, SessionDep],
) -> ReviewQueueSummaryResponse:
    return await AdjudicationService.get_review_summary(db=db, project_id=project_id)


@router.get(
    "/projects/{project_id}/review-queue",
    response_model=ReviewQueueListResponse,
    summary="Get Review Queue List",
    description="Retrieves prioritized candidate pairs requiring human adjudication with multi-criteria filtering.",
)
async def get_review_queue(
    project_id: Annotated[uuid.UUID, Path(..., description="Project workspace identifier")],
    db: Annotated[AsyncSession, SessionDep],
    severity: Optional[str] = Query(None, description="Filter by conflict severity: CRITICAL, HIGH, MEDIUM, LOW, or ALL"),
    conflict_type: Optional[str] = Query(None, description="Filter by conflict type name"),
    bucket: Optional[str] = Query(None, description="Filter by confidence bucket: HIGH, MEDIUM, LOW, AMBIGUOUS, or ALL"),
    validation_status: Optional[str] = Query(None, description="Filter by validation status: PASS, WARNING, FAIL, or ALL"),
    adjudication_status: Optional[str] = Query(None, description="Filter by adjudication status: UNRESOLVED, RESOLVED, REJECTED, or ALL"),
    search: Optional[str] = Query(None, description="Search term matching parcel/record identifier"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
) -> ReviewQueueListResponse:
    return await AdjudicationService.get_review_queue(
        db=db,
        project_id=project_id,
        severity=severity,
        conflict_type=conflict_type,
        bucket=bucket,
        validation_status=validation_status,
        adjudication_status=adjudication_status,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/projects/{project_id}/review-queue/{record_id}",
    response_model=ReviewQueueItem,
    summary="Get Review Item Detail",
    description="Retrieves complete inspection details, geometry metrics, attribute differences, and conflict history for a candidate pair.",
)
async def get_review_item_detail(
    project_id: Annotated[uuid.UUID, Path(..., description="Project workspace identifier")],
    record_id: Annotated[str, Path(..., description="Harmonized record identifier")],
    db: Annotated[AsyncSession, SessionDep],
) -> ReviewQueueItem:
    return await AdjudicationService.get_review_item_detail(
        db=db, project_id=project_id, record_id=record_id
    )


@router.post(
    "/projects/{project_id}/review-queue/{record_id}/adjudicate",
    response_model=AdjudicationActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Adjudication Decision",
    description="Submits an explicit reviewer action (ACCEPT_SOURCE_A, ACCEPT_SOURCE_B, MERGE_RECONCILE, REJECT_UNRESOLVED) with notes and field reconciliations.",
)
async def adjudicate_record(
    project_id: Annotated[uuid.UUID, Path(..., description="Project workspace identifier")],
    record_id: Annotated[str, Path(..., description="Harmonized record identifier")],
    request: AdjudicationActionRequest,
    db: Annotated[AsyncSession, SessionDep],
) -> AdjudicationActionResponse:
    return await AdjudicationService.adjudicate_record(
        db=db, project_id=project_id, record_id=record_id, request=request
    )


@router.post(
    "/projects/{project_id}/pipeline/stage-11/execute",
    response_model=Stage11ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute / Finalize Stage 11 Human Review",
    description="Evaluates completion of the human review queue. Transitions Stage 11 to completed if all mandatory records are adjudicated.",
)
@router.post(
    "/projects/{project_id}/review-queue/finalize",
    response_model=Stage11ExecutionResponse,
    include_in_schema=False,
)
async def execute_stage_11(
    project_id: Annotated[uuid.UUID, Path(..., description="Project workspace identifier")],
    db: Annotated[AsyncSession, SessionDep],
) -> Stage11ExecutionResponse:
    return await AdjudicationService.finalize_stage_11(db=db, project_id=project_id)
