import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.schemas.spatial_analysis import (
    ProximityAnalysisRequest,
    BufferAnalysisRequest,
    IntersectionAnalysisRequest,
    ContainmentAnalysisRequest,
    NearestFeaturesRequest,
    SpatialStatisticsRequest,
    DatasetComparisonRequest,
    SpatialConflictAnalysisRequest,
    SpatialAnalysisResult,
    DatasetComparisonResult,
    SpatialConflictAnalysisResult,
    VersionComparisonRequest,
    VersionComparisonResult,
    AnalysisHistorySummary,
)
from app.services.spatial_analysis.service import SpatialAnalysisService
from app.services.spatial_analysis.history import AnalysisHistoryService
from app.services.spatial_analysis.export import AnalysisExportService

router = APIRouter()


@router.post(
    "/proximity",
    response_model=SpatialAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Execute PostGIS proximity search",
    description="Finds features located within a specified radius (in meters) of a target point or feature using PostGIS ST_DWithin.",
)
async def proximity_analysis(
    request: ProximityAnalysisRequest,
    db: AsyncSession = SessionDep,
) -> SpatialAnalysisResult:
    try:
        return await SpatialAnalysisService.find_features_within_distance(db, request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Proximity analysis failed: {str(e)}",
        )


@router.post(
    "/buffer",
    response_model=SpatialAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Execute analytical spatial buffer",
    description="Constructs an analytical PostGIS spatial buffer (without database mutation) and computes intersecting features.",
)
async def buffer_analysis(
    request: BufferAnalysisRequest,
    db: AsyncSession = SessionDep,
) -> SpatialAnalysisResult:
    try:
        return await SpatialAnalysisService.create_analysis_buffer(db, request)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Buffer analysis failed: {str(e)}",
        )


@router.post(
    "/intersection",
    response_model=SpatialAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Execute PostGIS intersection analysis",
    description="Detects intersecting feature pairs and computes intersection geometries and overlap areas between two datasets.",
)
async def intersection_analysis(
    request: IntersectionAnalysisRequest,
    db: AsyncSession = SessionDep,
) -> SpatialAnalysisResult:
    try:
        return await SpatialAnalysisService.find_intersections(db, request)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intersection analysis failed: {str(e)}",
        )


@router.post(
    "/containment",
    response_model=SpatialAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Execute spatial containment analysis",
    description="Evaluates ST_Contains / ST_Within relationships between container zoning/parcels and contained structures.",
)
async def containment_analysis(
    request: ContainmentAnalysisRequest,
    db: AsyncSession = SessionDep,
) -> SpatialAnalysisResult:
    try:
        return await SpatialAnalysisService.find_containment(db, request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Containment analysis failed: {str(e)}",
        )


@router.post(
    "/nearest",
    response_model=SpatialAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Find nearest neighboring features",
    description="Identifies top-k nearest spatial features ordered by PostGIS ST_Distance.",
)
async def nearest_features(
    request: NearestFeaturesRequest,
    db: AsyncSession = SessionDep,
) -> SpatialAnalysisResult:
    try:
        return await SpatialAnalysisService.find_nearest_features(db, request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Nearest neighbor search failed: {str(e)}",
        )


@router.post(
    "/statistics",
    response_model=SpatialAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Compute spatial coverage and geometry statistics",
    description="Calculates bounding box extents, total polygon area in square meters, geometry types, and validity percentage.",
)
async def spatial_statistics(
    request: SpatialStatisticsRequest,
    db: AsyncSession = SessionDep,
) -> SpatialAnalysisResult:
    try:
        return await SpatialAnalysisService.calculate_spatial_statistics(db, request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Spatial statistics computation failed: {str(e)}",
        )


@router.post(
    "/compare",
    response_model=DatasetComparisonResult,
    status_code=status.HTTP_200_OK,
    summary="Comprehensive spatial dataset comparison",
    description="Performs deep pairwise spatial comparison between two datasets: overlap %, unmatched counts, and classified GeoJSON layers.",
)
async def compare_datasets(
    request: DatasetComparisonRequest,
    db: AsyncSession = SessionDep,
) -> DatasetComparisonResult:
    try:
        return await SpatialAnalysisService.compare_datasets_spatially(db, request)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dataset comparison failed: {str(e)}",
        )


@router.post(
    "/conflicts",
    response_model=SpatialConflictAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Geographic conflict clustering and density analysis",
    description="Analyzes spatial concentration of unresolved attribute conflicts and identifies hotspot clusters and dataset disagreements.",
)
async def analyze_conflicts_spatially(
    request: SpatialConflictAnalysisRequest,
    db: AsyncSession = SessionDep,
) -> SpatialConflictAnalysisResult:
    try:
        return await SpatialAnalysisService.analyze_conflicts_spatially(db, request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Spatial conflict analysis failed: {str(e)}",
        )


@router.post(
    "/versions/compare",
    response_model=VersionComparisonResult,
    status_code=status.HTTP_200_OK,
    summary="Compare two dataset versions (temporal intelligence)",
    description="Detects added, removed, changed, and unchanged features between two versions of the same dataset. Gracefully handles single-version datasets without fabricating temporal data.",
)
async def compare_dataset_versions(
    request: VersionComparisonRequest,
    db: AsyncSession = SessionDep,
) -> VersionComparisonResult:
    try:
        return await SpatialAnalysisService.compare_dataset_versions(db, request)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dataset version comparison failed: {str(e)}",
        )


@router.get(
    "/history",
    response_model=List[AnalysisHistorySummary],
    status_code=status.HTTP_200_OK,
    summary="List recent spatial analysis history",
    description="Returns recent spatial analysis runs with execution parameters, result counts, and timing.",
)
async def get_analysis_history(
    project_id: Optional[uuid.UUID] = Query(None, description="Filter history by project ID"),
) -> List[AnalysisHistorySummary]:
    return AnalysisHistoryService.get_history(project_id)


@router.get(
    "/{analysis_id}",
    response_model=SpatialAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Get spatial analysis result by ID",
    description="Retrieves a complete spatial analysis result from history for re-visualization on the map.",
)
async def get_analysis_by_id(
    analysis_id: uuid.UUID,
) -> SpatialAnalysisResult:
    result = AnalysisHistoryService.get_analysis(analysis_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis result {analysis_id} not found in active session history.",
        )
    return result


@router.post(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Export spatial analysis result as GeoJSON or CSV",
    description="Exports a real spatial analysis result as valid RFC 7946 GeoJSON or flattened CSV.",
)
async def export_analysis_result(
    result: SpatialAnalysisResult,
    format: str = Query("geojson", description="Export format: 'geojson' or 'csv'"),
) -> Response:
    filename_prefix = f"landsync_{result.analysis_type.value.lower()}_{str(result.analysis_id)[:8]}"
    if format.lower() == "csv":
        csv_content = AnalysisExportService.to_csv(result)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename_prefix}.csv"'},
        )
    else:
        geojson_content = AnalysisExportService.to_geojson(result)
        return Response(
            content=geojson_content,
            media_type="application/geo+json",
            headers={"Content-Disposition": f'attachment; filename="{filename_prefix}.geojson"'},
        )


@router.get(
    "/{analysis_id}/export",
    status_code=status.HTTP_200_OK,
    summary="Export historical spatial analysis result by ID",
    description="Retrieves analysis from history and downloads as GeoJSON or CSV.",
)
async def export_analysis_by_id(
    analysis_id: uuid.UUID,
    format: str = Query("geojson", description="Export format: 'geojson' or 'csv'"),
) -> Response:
    result = AnalysisHistoryService.get_analysis(analysis_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis result {analysis_id} not found in history for export.",
        )
    filename_prefix = f"landsync_{result.analysis_type.value.lower()}_{str(result.analysis_id)[:8]}"
    if format.lower() == "csv":
        csv_content = AnalysisExportService.to_csv(result)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename_prefix}.csv"'},
        )
    else:
        geojson_content = AnalysisExportService.to_geojson(result)
        return Response(
            content=geojson_content,
            media_type="application/geo+json",
            headers={"Content-Disposition": f'attachment; filename="{filename_prefix}.geojson"'},
        )
