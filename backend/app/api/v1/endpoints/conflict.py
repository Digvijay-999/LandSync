import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.services.conflict.service import ConflictDetectionService
from app.schemas.conflict import (
    AttributeConflictRead,
    ConflictResolveInput,
    ConflictDismissInput,
    ConflictListResponse,
    ConflictSummaryResponse,
)

router = APIRouter()


@router.get(
    "/unified-records/{record_id}/conflicts",
    response_model=List[AttributeConflictRead],
    status_code=status.HTTP_200_OK,
    summary="Get all attribute conflicts for an individual unified land record",
    description="Returns detected and resolved attribute conflicts with source evidence and resolution metadata.",
)
async def get_record_conflicts(
    record_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> List[AttributeConflictRead]:
    try:
        return await ConflictDetectionService.get_record_conflicts(db, record_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch record conflicts: {str(e)}",
        )


@router.get(
    "/projects/{project_id}/conflicts",
    response_model=ConflictListResponse,
    status_code=status.HTTP_200_OK,
    summary="List paginated attribute conflicts for a project",
    description="Filterable by status (UNRESOLVED, RESOLVED, DISMISSED), attribute_name, and severity.",
)
async def list_project_conflicts(
    project_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (UNRESOLVED, RESOLVED, DISMISSED, ALL)"),
    attribute_name: Optional[str] = Query(None, description="Filter by attribute name (e.g. land_use, area)"),
    severity: Optional[str] = Query(None, description="Filter by severity (HIGH, MEDIUM, LOW)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = SessionDep,
) -> ConflictListResponse:
    try:
        return await ConflictDetectionService.get_project_conflicts(
            db,
            project_id=project_id,
            status=status_filter,
            attribute_name=attribute_name,
            severity=severity,
            skip=skip,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list project conflicts: {str(e)}",
        )


@router.get(
    "/projects/{project_id}/conflicts/summary",
    response_model=ConflictSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project-level conflict dashboard statistics",
    description="Returns aggregate counts of total, unresolved, resolved, and dismissed conflicts across records.",
)
async def get_project_conflict_summary(
    project_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> ConflictSummaryResponse:
    try:
        return await ConflictDetectionService.get_project_conflict_summary(db, project_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conflict summary: {str(e)}",
        )


@router.get(
    "/conflicts/{conflict_id}",
    response_model=AttributeConflictRead,
    status_code=status.HTTP_200_OK,
    summary="Get conflict details and evidence",
    description="Returns detailed source values, conflict classification, and resolution history.",
)
async def get_conflict_detail(
    conflict_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> AttributeConflictRead:
    conflict = await ConflictDetectionService.get_conflict_detail(db, conflict_id)
    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attribute conflict with ID '{conflict_id}' not found.",
        )
    return conflict


@router.post(
    "/conflicts/{conflict_id}/resolve",
    response_model=AttributeConflictRead,
    status_code=status.HTTP_200_OK,
    summary="Resolve an attribute conflict",
    description="Executes a human resolution via SOURCE_SELECTION or MANUAL_VALUE with mandatory audit notes.",
)
async def resolve_conflict(
    conflict_id: uuid.UUID,
    input_data: ConflictResolveInput,
    db: AsyncSession = SessionDep,
) -> AttributeConflictRead:
    try:
        return await ConflictDetectionService.resolve_conflict(db, conflict_id, input_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve conflict: {str(e)}",
        )


@router.post(
    "/conflicts/{conflict_id}/dismiss",
    response_model=AttributeConflictRead,
    status_code=status.HTTP_200_OK,
    summary="Dismiss an attribute conflict",
    description="Dismisses a conflict with a mandatory audit reason.",
)
async def dismiss_conflict(
    conflict_id: uuid.UUID,
    input_data: ConflictDismissInput,
    db: AsyncSession = SessionDep,
) -> AttributeConflictRead:
    try:
        return await ConflictDetectionService.dismiss_conflict(db, conflict_id, input_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dismiss conflict: {str(e)}",
        )
