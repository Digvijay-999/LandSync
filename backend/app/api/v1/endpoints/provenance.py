import uuid
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.services.provenance.service import ProvenanceService
from app.schemas.provenance import (
    UnifiedRecordProvenanceResponse,
    ProjectProvenanceSummaryResponse,
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
    summary="Get project-level provenance and audit summary",
    description="Returns aggregate provenance counts, datasets involved in harmonization, and recent audit events.",
)
async def get_project_provenance_summary(
    project_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> ProjectProvenanceSummaryResponse:
    try:
        return await ProvenanceService.get_project_provenance_summary(db, project_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate project provenance summary: {str(e)}",
        )
