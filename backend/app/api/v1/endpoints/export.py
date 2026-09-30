import json
import uuid
from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
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
