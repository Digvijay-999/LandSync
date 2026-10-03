import uuid
from typing import Optional, List, Union, Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.services.conflict.service import ConflictDetectionService
from app.schemas.conflict import (
    AttributeConflictRead,
    ConflictResolveInput,
    ConflictDismissInput,
    ConflictListResponse,
    ConflictSummaryResponse,
    GeospatialConflictRead,
    GeospatialConflictStatusUpdate,
    GeospatialConflictListResponse,
)
from app.schemas.conflict_proposal import ConflictResolutionProposal
from app.models.conflict import AttributeConflict, GeospatialConflict
from app.services.assistant.conflict_advisor import ConflictAdvisorService

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
    response_model=Union[GeospatialConflictListResponse, ConflictListResponse],
    status_code=status.HTTP_200_OK,
    summary="List paginated conflicts for a project",
    description="Returns Stage 08 Geospatial Conflicts if present, or legacy attribute conflicts. Supports filtering by severity, conflict_type, category, status, source, and search.",
)
async def list_project_conflicts(
    project_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (OPEN, ACKNOWLEDGED, RESOLVED, DISMISSED, ALL)"),
    conflict_type: Optional[str] = Query(None, description="Filter by conflict type (e.g. AREA_DISCREPANCY, LAND_USE_CONFLICT, etc.)"),
    category: Optional[str] = Query(None, description="Filter by category (e.g. GEOMETRY, SEMANTIC, REGISTRY, RISK)"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)"),
    source: Optional[str] = Query(None, description="Filter by dataset or source name"),
    search: Optional[str] = Query(None, description="Filter by parcel/record identifier or keyword"),
    attribute_name: Optional[str] = Query(None, description="Legacy attribute name filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = SessionDep,
) -> Any:
    try:
        # Check if Stage 08 Geospatial Conflicts exist for this project
        count_stmt = select(func.count(GeospatialConflict.id)).where(GeospatialConflict.project_id == project_id)
        geo_count = (await db.execute(count_stmt)).scalar() or 0

        if geo_count > 0 or conflict_type or category or source or search:
            return await ConflictDetectionService.list_geospatial_conflicts(
                db,
                project_id=project_id,
                severity=severity,
                conflict_type=conflict_type,
                category=category,
                status=status_filter,
                source=source,
                search=search,
                skip=skip,
                limit=limit,
            )
        else:
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
    response_model=Union[GeospatialConflictRead, AttributeConflictRead],
    status_code=status.HTTP_200_OK,
    summary="Get conflict details and evidence",
    description="Returns detailed source values, spatial evidence, and conflict classification.",
)
async def get_conflict_detail(
    conflict_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> Any:
    # 1. Try finding in Stage 08 Geospatial Conflicts
    geo_conflict = await ConflictDetectionService.get_geospatial_conflict(db, conflict_id)
    if geo_conflict:
        return geo_conflict

    # 2. Fall back to AttributeConflict
    attr_conflict = await ConflictDetectionService.get_conflict_detail(db, conflict_id)
    if attr_conflict:
        return attr_conflict

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Conflict with ID '{conflict_id}' not found.",
    )


@router.patch(
    "/conflicts/{conflict_id}",
    response_model=Union[GeospatialConflictRead, AttributeConflictRead],
    status_code=status.HTTP_200_OK,
    summary="Update conflict status",
    description="Updates conflict status (OPEN, ACKNOWLEDGED, RESOLVED, DISMISSED) with optional notes.",
)
async def update_conflict_status(
    conflict_id: uuid.UUID,
    input_data: GeospatialConflictStatusUpdate,
    db: AsyncSession = SessionDep,
) -> Any:
    # 1. Try finding in Stage 08 Geospatial Conflicts
    geo = await db.get(GeospatialConflict, conflict_id)
    if geo:
        try:
            return await ConflictDetectionService.update_geospatial_conflict_status(
                db, conflict_id, input_data
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 2. Try finding in AttributeConflict
    attr = await db.get(AttributeConflict, conflict_id)
    if attr:
        if input_data.status.upper() == "RESOLVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use POST /conflicts/{conflict_id}/resolve to provide resolution evidence for unified record conflicts.",
            )
        elif input_data.status.upper() == "DISMISSED":
            return await ConflictDetectionService.dismiss_conflict(
                db, conflict_id, ConflictDismissInput(reason=input_data.notes or "Dismissed via status update")
            )
        else:
            attr.status = input_data.status.upper()
            await db.commit()
            await db.refresh(attr)
            return await ConflictDetectionService.get_conflict_detail(db, conflict_id)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Conflict with ID '{conflict_id}' not found.",
    )


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


@router.post(
    "/conflicts/{conflict_id}/propose-resolution",
    response_model=ConflictResolutionProposal,
    status_code=status.HTTP_200_OK,
    summary="Generate advisory AI conflict-resolution proposal",
    description="Analyzes conflicting source values, domain authorities, and provenance to produce a strictly advisory recommendation without mutating the database.",
)
async def propose_conflict_resolution(
    conflict_id: uuid.UUID,
    project_id: Optional[uuid.UUID] = Query(None, description="Optional project workspace ID"),
    db: AsyncSession = SessionDep,
) -> ConflictResolutionProposal:
    if not project_id:
        conf_obj = await db.get(AttributeConflict, conflict_id)
        if not conf_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conflict {conflict_id} not found",
            )
        project_id = conf_obj.project_id

    proposal = await ConflictAdvisorService.generate_proposal(db, project_id, conflict_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conflict {conflict_id} not found in project {project_id}",
        )
    return proposal
