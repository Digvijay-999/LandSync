import json
import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.schemas.export import ExportCreateRequest, ExportJobItem, ExportJobListResponse
from app.services.export.service import ExportService

router = APIRouter()


@router.get(
    "/projects/{project_id}/exports/unified-records.geojson",
    status_code=status.HTTP_200_OK,
    summary="Export all unified records for a project as GeoJSON",
    description="Returns an RFC 7946 GeoJSON FeatureCollection of canonical land records with metadata and provenance properties.",
)
async def export_project_geojson(
    project_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> Response:
    try:
        data, filename = await ExportService.export_project_geojson(db, project_id)
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/geo+json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export project GeoJSON: {str(e)}",
        )


@router.get(
    "/projects/{project_id}/exports/unified-records.csv",
    status_code=status.HTTP_200_OK,
    summary="Export all unified records for a project as CSV",
    description="Returns a CSV file containing all unified land records and contributing provenance columns.",
)
async def export_project_csv(
    project_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> Response:
    try:
        csv_content, filename = await ExportService.export_project_csv(db, project_id)
        return Response(
            content=csv_content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export project CSV: {str(e)}",
        )


@router.get(
    "/unified-records/{record_id}/export.geojson",
    status_code=status.HTTP_200_OK,
    summary="Export an individual unified record as GeoJSON",
    description="Returns a valid GeoJSON Feature representing the unified record with canonical geometry and properties.",
)
async def export_single_record_geojson(
    record_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> Response:
    try:
        data, filename = await ExportService.export_single_record_geojson(db, record_id)
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/geo+json",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export record GeoJSON: {str(e)}",
        )


@router.get(
    "/unified-records/{record_id}/export.csv",
    status_code=status.HTTP_200_OK,
    summary="Export an individual unified record as CSV",
    description="Returns a CSV file representing the individual unified record with provenance columns.",
)
async def export_single_record_csv(
    record_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> Response:
    try:
        csv_content, filename = await ExportService.export_single_record_csv(db, record_id)
        return Response(
            content=csv_content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export record CSV: {str(e)}",
        )


# =============================================================================
# STAGE 14: PERSISTENT DELIVERABLES & DOWNLOADS
# =============================================================================

@router.post(
    "/projects/{project_id}/exports",
    response_model=ExportJobItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create Authoritative Deliverable Export",
    description="Generates an authoritative geospatial export (GeoJSON, GeoPackage, CSV) with cryptographic verification and metadata manifest.",
)
async def create_project_export(
    project_id: uuid.UUID,
    req: ExportCreateRequest,
    db: AsyncSession = SessionDep,
) -> ExportJobItem:
    return await ExportService.create_export_job(db=db, project_id=project_id, req=req)


@router.get(
    "/projects/{project_id}/exports",
    response_model=ExportJobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Project Export Deliverables",
    description="Lists previously generated export deliverable artifacts and their download references.",
)
async def list_project_exports(
    project_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> ExportJobListResponse:
    return await ExportService.list_project_exports(db=db, project_id=project_id)


@router.get(
    "/projects/{project_id}/exports/{export_id}",
    response_model=ExportJobItem,
    status_code=status.HTTP_200_OK,
    summary="Get Export Deliverable Metadata",
    description="Retrieves metadata, record counts, and status for a specific export job.",
)
async def get_project_export(
    project_id: uuid.UUID,
    export_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> ExportJobItem:
    return await ExportService.get_export_job_item(db=db, project_id=project_id, export_id=export_id)


@router.get(
    "/projects/{project_id}/exports/{export_id}/manifest",
    status_code=status.HTTP_200_OK,
    summary="Get Export Manifest",
    description="Retrieves the defensible provenance manifest for an export deliverable.",
)
async def get_project_export_manifest(
    project_id: uuid.UUID,
    export_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> Dict[str, Any]:
    return await ExportService.get_export_manifest(db=db, project_id=project_id, export_id=export_id)


@router.get(
    "/projects/{project_id}/exports/{export_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download Export Deliverable File",
    description="Securely downloads the generated geospatial deliverable file (GeoJSON, GeoPackage, or CSV) with proper Content-Disposition header.",
)
async def download_project_export(
    project_id: uuid.UUID,
    export_id: uuid.UUID,
    db: AsyncSession = SessionDep,
) -> FileResponse:
    file_path, filename, media_type = await ExportService.download_export_file(
        db=db, project_id=project_id, export_id=export_id
    )
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
    )

