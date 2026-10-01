import uuid
from typing import Annotated, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    UploadFile,
    File,
    Form,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import SessionDep
from app.schemas.dataset import (
    DatasetRead,
    DatasetDetailResponse,
    DatasetListResponse,
    DatasetProfile,
    DatasetVersionRead,
    BoundingBox,
)
from app.schemas.feature import (
    GeoJSONFeatureCollection,
    FeatureListResponse,
)
from app.services.dataset import DatasetService
from app.services.ingestion.exceptions import (
    IngestionError,
    UnsupportedFormatError,
    FileTooLargeError,
    CorruptedFileError,
    MissingShapefileComponentsError,
    MissingCoordinateColumnsError,
    EmptyDatasetError,
    InvalidCoordinateError,
    ProjectNotFoundError,
)
from app.services.crs.normalizer import (
    MissingCRSError,
    InvalidCRSError,
    TransformationError,
)

router = APIRouter()


@router.post(
    "/projects/{project_id}/datasets",
    response_model=DatasetDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload & Ingest Dataset",
    description="Uploads a vector dataset (GeoJSON, Shapefile ZIP, GeoPackage, CSV), performs profiling, and registers it in the project.",
)
async def upload_dataset(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    file: UploadFile = File(..., description="Geospatial data file"),
    name: Optional[str] = Form(None, description="Optional custom dataset name"),
    crs: Optional[str] = Form(None, description="Optional CRS override (e.g. EPSG:4326 for CSV)"),
) -> DatasetDetailResponse:
    """Thin route handler delegating file handling and profiling to DatasetService."""
    try:
        dataset = await DatasetService.ingest_dataset(
            db=db,
            project_id=project_id,
            file=file,
            custom_name=name,
            custom_crs=crs,
        )
    except ProjectNotFoundError as pne:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=pne.message)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except FileTooLargeError as fe:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=fe.message)
    except (
        UnsupportedFormatError,
        MissingShapefileComponentsError,
        MissingCoordinateColumnsError,
        InvalidCoordinateError,
        EmptyDatasetError,
    ) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except (MissingCRSError, InvalidCRSError) as crs_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=crs_err.message)
    except TransformationError as trans_err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=trans_err.message)
    except CorruptedFileError as ce:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=ce.message)
    except IngestionError as ie:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ie.message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during dataset ingestion: {str(exc)}",
        )

    # Convert bounding box
    bbox_obj = BoundingBox(**dataset.bounding_box) if dataset.bounding_box else None
    profile_obj = DatasetProfile(**dataset.profile_metadata) if dataset.profile_metadata else None
    versions_list = [
        DatasetVersionRead.model_validate(v) for v in (dataset.versions or [])
    ]

    return DatasetDetailResponse(
        id=dataset.id,
        project_id=dataset.project_id,
        name=dataset.name,
        source_filename=dataset.source_filename,
        source_format=dataset.source_format,
        source_type=dataset.source_type,
        status=dataset.status,
        feature_count=dataset.feature_count,
        geometry_type=dataset.geometry_type,
        detected_crs=dataset.detected_crs,
        bounding_box=bbox_obj,
        file_size=dataset.file_size,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        profile=profile_obj,
        versions=versions_list,
    )


@router.get(
    "/projects/{project_id}/datasets",
    response_model=DatasetListResponse,
    summary="List Project Datasets",
    description="Lists all vector datasets ingested for a specific project.",
)
async def list_project_datasets(
    project_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> DatasetListResponse:
    items, total = await DatasetService.list_datasets(db, project_id=project_id, skip=skip, limit=limit)
    return DatasetListResponse(
        items=[
            DatasetRead(
                id=d.id,
                project_id=d.project_id,
                name=d.name,
                source_filename=d.source_filename,
                source_format=d.source_format,
                source_type=d.source_type,
                status=d.status,
                feature_count=d.feature_count,
                geometry_type=d.geometry_type,
                detected_crs=d.detected_crs,
                bounding_box=BoundingBox(**d.bounding_box) if d.bounding_box else None,
                file_size=d.file_size,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in items
        ],
        total=total,
    )


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetDetailResponse,
    summary="Get Dataset Details",
    description="Retrieves dataset metadata, profiling summary, and version history.",
)
async def get_dataset(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> DatasetDetailResponse:
    dataset = await DatasetService.get_dataset(db, dataset_id=dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID '{dataset_id}' not found.",
        )

    bbox_obj = BoundingBox(**dataset.bounding_box) if dataset.bounding_box else None
    profile_obj = DatasetProfile(**dataset.profile_metadata) if dataset.profile_metadata else None
    versions_list = [
        DatasetVersionRead.model_validate(v) for v in (dataset.versions or [])
    ]

    return DatasetDetailResponse(
        id=dataset.id,
        project_id=dataset.project_id,
        name=dataset.name,
        source_filename=dataset.source_filename,
        source_format=dataset.source_format,
        source_type=dataset.source_type,
        status=dataset.status,
        feature_count=dataset.feature_count,
        geometry_type=dataset.geometry_type,
        detected_crs=dataset.detected_crs,
        bounding_box=bbox_obj,
        file_size=dataset.file_size,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        profile=profile_obj,
        versions=versions_list,
    )


@router.get(
    "/datasets/{dataset_id}/profile",
    response_model=DatasetProfile,
    summary="Get Dataset Profile",
    description="Retrieves the detailed geometric, spatial, and attribute profile of an ingested dataset.",
)
async def get_dataset_profile(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> DatasetProfile:
    dataset = await DatasetService.get_dataset(db, dataset_id=dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID '{dataset_id}' not found.",
        )

    if not dataset.profile_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Profile metadata for dataset '{dataset_id}' is not available.",
        )

    return DatasetProfile(**dataset.profile_metadata)


@router.delete(
    "/datasets/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Dataset",
    description="Removes the dataset record, versions, and physical storage files.",
)
async def delete_dataset(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
) -> None:
    deleted = await DatasetService.delete_dataset(db, dataset_id=dataset_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID '{dataset_id}' not found.",
        )


@router.get(
    "/datasets/{dataset_id}/features",
    response_model=FeatureListResponse,
    summary="Get Dataset Features",
    description="Retrieves paginated features (properties and metadata) for a dataset.",
)
async def get_dataset_features(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    representation: str = Query(default="canonical", description="Representation type: 'canonical' or 'source'"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
) -> FeatureListResponse:
    try:
        items, total = await DatasetService.get_dataset_features(
            db=db,
            dataset_id=dataset_id,
            representation=representation,
            skip=skip,
            limit=limit,
        )
        return FeatureListResponse(items=items, total=total)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get(
    "/datasets/{dataset_id}/features/geojson",
    response_model=GeoJSONFeatureCollection,
    summary="Get Dataset Features as GeoJSON",
    description="Retrieves dataset features formatted as a standard GeoJSON FeatureCollection for MapLibre rendering.",
)
async def get_dataset_features_geojson(
    dataset_id: uuid.UUID,
    db: Annotated[AsyncSession, SessionDep],
    representation: str = Query(default="canonical", description="Projection representation: 'canonical' (project CRS) or 'source' (source CRS)"),
    limit: int = Query(default=5000, ge=1, le=10000),
) -> GeoJSONFeatureCollection:
    try:
        return await DatasetService.get_dataset_features_geojson(
            db=db,
            dataset_id=dataset_id,
            representation=representation,
            limit=limit,
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
