import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.services.unified.service import UnifiedRecordService
from app.schemas.unified import (
    UnifiedRecordSourceResponse,
    UnifiedRecordListItem,
    UnifiedRecordListResponse,
    UnifiedRecordDetailResponse,
    UnifiedRecordBuildResponse,
    UnifiedRecordStatisticsResponse,
)

router = APIRouter()


@router.post(
    "/projects/{project_id}/unified-records/build",
    response_model=UnifiedRecordBuildResponse,
    status_code=status.HTTP_200_OK,
    summary="Build or update unified land records from accepted matches",
    description="Idempotently groups accepted candidate relationships into unified records, detects conflicts, and selects canonical geometry.",
)
async def build_unified_records(
    project_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> UnifiedRecordBuildResponse:
    try:
        return await UnifiedRecordService.build_records_from_accepted_matches(
            db, project_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build unified records: {str(e)}",
        )


@router.get(
    "/projects/{project_id}/unified-records",
    response_model=UnifiedRecordListResponse,
    status_code=status.HTTP_200_OK,
    summary="List unified land records for a project",
    description="Returns a paginated list of unified records, filterable by status, resolution_status, and search query.",
)
async def list_unified_records(
    project_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (ACTIVE, INCOMPLETE, CONFLICT)"),
    resolution_status: Optional[str] = Query(None, description="Filter by resolution status (UNIFIED, REJECTED)"),
    search: Optional[str] = Query(None, description="Search query across parcel IDs and source references"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = SessionDep,
) -> UnifiedRecordListResponse:
    return await UnifiedRecordService.get_records(
        db,
        project_id,
        status=status_filter,
        resolution_status=resolution_status,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/projects/{project_id}/unified-records/statistics",
    response_model=UnifiedRecordStatisticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project-level unified record metrics",
    description="Returns aggregate database counts for active, incomplete, and conflict records, plus source role distribution.",
)
async def get_unified_record_statistics(
    project_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> UnifiedRecordStatisticsResponse:
    return await UnifiedRecordService.get_statistics(db, project_id)


@router.get(
    "/projects/{project_id}/unified-records/{record_id}",
    response_model=UnifiedRecordDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get comprehensive unified land record details under project",
    description="Returns canonical geometry GeoJSON, canonical attributes, source count, status, and contributing source features.",
)
async def get_project_unified_record_detail(
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> UnifiedRecordDetailResponse:
    record = await UnifiedRecordService.get_record_detail(db, record_id)
    if not record or record.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unified land record with ID '{record_id}' not found for project '{project_id}'.",
        )
    return record


@router.get(
    "/unified-records/{record_id}",
    response_model=UnifiedRecordDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get comprehensive unified land record details",
    description="Returns canonical geometry GeoJSON, canonical attributes, source count, status, and contributing source features.",
)
async def get_unified_record_detail(
    record_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> UnifiedRecordDetailResponse:
    record = await UnifiedRecordService.get_record_detail(db, record_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unified land record with ID '{record_id}' not found.",
        )
    return record


@router.get(
    "/unified-records/{record_id}/sources",
    response_model=List[UnifiedRecordSourceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get contributing source features for a unified land record",
    description="Returns all contributing source features with original geometries and properties.",
)
async def get_unified_record_sources(
    record_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> List[UnifiedRecordSourceResponse]:
    record = await UnifiedRecordService.get_record_detail(db, record_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unified land record with ID '{record_id}' not found.",
        )
    return record.sources
