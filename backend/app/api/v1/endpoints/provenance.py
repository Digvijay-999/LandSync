import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.services.provenance.service import ProvenanceService
from app.schemas.provenance import (
    UnifiedRecordProvenanceResponse,
    ProjectProvenanceSummaryResponse,
    ProvenanceRecordDetailResponse,
    ProvenanceTimelineItem,
    ProvenanceSourceItem,
)

router = APIRouter()


@router.get(
    "/unified-records/{record_id}/provenance",
    response_model=UnifiedRecordProvenanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get complete provenance chain for an individual unified land record",
    description="Returns contributing source features, datasets, accepted match relationships, machine scores, candidate rank, human reviews, and chronological lifecycle timeline.",
)
async def get_unified_record_provenance(
    record_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> UnifiedRecordProvenanceResponse:
    provenance = await ProvenanceService.get_record_provenance(db, record_id)
    if not provenance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unified land record with ID '{record_id}' not found.",
        )
    return provenance


@router.get(
    "/projects/{project_id}/provenance",
    response_model=ProjectProvenanceSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project-level provenance summary and queryable records",
    description="Returns aggregate provenance counts, datasets involved in harmonization, recent audit events, and paginated filterable records.",
)
async def get_project_provenance(
    project_id: uuid.UUID,
    db: AsyncSession = SessionDep,
    search: Optional[str] = Query(None, description="Search by record identifier or harmonized ID"),
    status: Optional[str] = Query(None, description="Filter by lineage status (ALL, COMPLETE, PARTIAL, QUARANTINED, UNIFIED, REJECTED)"),
    status_filter: Optional[str] = Query(None, description="Alias for status filter"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
) -> ProjectProvenanceSummaryResponse:
    try:
        effective_filter = status_filter if status_filter is not None else status
        return await ProvenanceService.get_project_provenance_records(
            db=db,
            project_id=project_id,
            search=search,
            status_filter=effective_filter,
            skip=skip,
            limit=limit,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate project provenance summary: {str(e)}",
        )


@router.get(
    "/projects/{project_id}/provenance/{unified_record_id}",
    response_model=ProvenanceRecordDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get comprehensive interactive lineage details for a single unified record",
    description="Returns complete upstream lineage including final record attributes, source features, processing metrics, human review decision, chronological timeline, and DAG graph.",
)
async def get_provenance_record_detail(
    project_id: uuid.UUID,
    unified_record_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> ProvenanceRecordDetailResponse:
    return await ProvenanceService.get_record_lineage_detail(
        db=db,
        project_id=project_id,
        record_id=unified_record_id,
    )


@router.get(
    "/projects/{project_id}/provenance/{unified_record_id}/timeline",
    response_model=List[ProvenanceTimelineItem],
    status_code=status.HTTP_200_OK,
    summary="Get chronological lifecycle timeline for a unified record",
    description="Returns verified chronological milestones in the lifecycle of the unified record from database evidence.",
)
async def get_provenance_timeline(
    project_id: uuid.UUID,
    unified_record_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> List[ProvenanceTimelineItem]:
    return await ProvenanceService.get_record_timeline(
        db=db,
        project_id=project_id,
        record_id=unified_record_id,
    )


@router.get(
    "/projects/{project_id}/provenance/{unified_record_id}/sources",
    response_model=List[ProvenanceSourceItem],
    status_code=status.HTTP_200_OK,
    summary="Get contributing source features and datasets for a unified record",
    description="Returns originating dataset versions and canonical source feature details for the unified record.",
)
async def get_provenance_sources(
    project_id: uuid.UUID,
    unified_record_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> List[ProvenanceSourceItem]:
    return await ProvenanceService.get_record_sources(
        db=db,
        project_id=project_id,
        record_id=unified_record_id,
    )
