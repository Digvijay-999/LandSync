import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import SessionDep
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectRead,
    ProjectListResponse,
)
from app.schemas.feature import ProjectLayersResponse, GeoJSONFeatureCollection
from app.services.project import ProjectService
from app.services.dataset import DatasetService

router = APIRouter()


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Project",
    description="Initializes a new geospatial harmonization project workspace.",
)
async def create_project(
    data: ProjectCreate,
    db: Annotated[AsyncSession, SessionDep],
) -> ProjectRead:
    """Thin route handler delegating to ProjectService."""
    project = await ProjectService.create_project(db, data)
    return ProjectRead.model_validate(project)


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List Projects",
    description="Retrieves a paginated list of geospatial projects.",
)
async def list_projects(
    db: Annotated[AsyncSession, SessionDep],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> ProjectListResponse:
    """Thin route handler delegating to ProjectService."""
    items, total = await ProjectService.list_projects(db, skip=skip, limit=limit)
    return ProjectListResponse(
        items=[ProjectRead.model_validate(p) for p in items],
        total=total,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
    summary="Get Project Details",
    description="Fetches a single project workspace by its unique identifier.",
)
async def get_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> ProjectRead:
    """Thin route handler delegating to ProjectService."""
    project = await ProjectService.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )
    return ProjectRead.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
    summary="Update Project",
    description="Updates metadata or target CRS for an existing project.",
)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: Annotated[AsyncSession, SessionDep],
) -> ProjectRead:
    """Thin route handler delegating to ProjectService."""
    project = await ProjectService.update_project(db, project_id, data)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )
    return ProjectRead.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Project",
    description="Removes a project workspace.",
)
async def delete_project(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> None:
    """Thin route handler delegating to ProjectService."""
    deleted = await ProjectService.delete_project(db, project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID '{project_id}' not found",
        )


@router.get(
    "/{project_id}/layers",
    response_model=ProjectLayersResponse,
    summary="Get Project Spatial Layers",
    description="Returns all active spatial dataset layers, extents, geometries, and colors for MapLibre map rendering.",
)
async def get_project_layers(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> ProjectLayersResponse:
    try:
        return await DatasetService.get_project_layers(db, project_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get(
    "/{project_id}/features/geojson",
    response_model=GeoJSONFeatureCollection,
    summary="Get Project Combined GeoJSON",
    description="Returns a single combined GeoJSON FeatureCollection of all canonical features across all project datasets.",
)
async def get_project_combined_geojson(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> GeoJSONFeatureCollection:
    try:
        return await DatasetService.get_project_combined_geojson(db, project_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
