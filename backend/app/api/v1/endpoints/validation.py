import uuid
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.services.validation.service import ValidationService
from app.schemas.validation import (
    ValidationResultRead,
    ValidationSummaryResponse,
    ValidationResultListResponse,
)

router = APIRouter()


@router.get(
    "/projects/{project_id}/validation-results",
    response_model=ValidationResultListResponse,
    status_code=status.HTTP_200_OK,
    summary="List paginated validation results for a project",
    description="Returns Stage 09 validation records with overall and sub-rule status breakdown, metric payloads, and failure/warning explanations.",
)
async def list_validation_results(
    project_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by overall status (PASS, WARNING, FAIL, ALL)"),
    category: Optional[str] = Query(None, description="Filter by sub-rule category (GEOMETRY, TOPOLOGY, AREA, SEMANTIC, CONFLICT)"),
    search: Optional[str] = Query(None, description="Filter by identifier or parcel ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = SessionDep,
) -> ValidationResultListResponse:
    try:
        return await ValidationService.list_validation_results(
            db=db,
            project_id=project_id,
            status=status_filter,
            category=category,
            search=search,
            skip=skip,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch validation results: {str(e)}",
        )


@router.get(
    "/projects/{project_id}/validation-summary",
    response_model=ValidationSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project validation summary statistics",
    description="Returns aggregate counts of PASS, WARNING, FAIL and failure counts categorized by geometry, topology, area, semantics, and conflicts.",
)
async def get_validation_summary(
    project_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> ValidationSummaryResponse:
    try:
        return await ValidationService.get_validation_summary(db=db, project_id=project_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute validation summary: {str(e)}",
        )


@router.get(
    "/validation-results/{result_id}",
    response_model=ValidationResultRead,
    status_code=status.HTTP_200_OK,
    summary="Get individual validation result detail",
    description="Returns comprehensive validation result record including PostGIS validity diagnostics, topological metrics, area tolerance details, and associated conflicts.",
)
async def get_validation_result_detail(
    result_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> Any:
    result = await ValidationService.get_validation_result_detail(db=db, result_id=result_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Validation result with ID '{result_id}' not found.",
        )
    return result
