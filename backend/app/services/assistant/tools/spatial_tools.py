import uuid
import math
from typing import Dict, Any, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shapely.geometry import Point, shape, mapping, Polygon, box
from shapely.ops import transform
import pyproj

from app.models.unified import UnifiedLandRecord
from app.models.feature import CanonicalFeature


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in meters."""
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


async def find_records_near_coordinates(
    db: AsyncSession,
    project_id: uuid.UUID,
    latitude: float,
    longitude: float,
    radius_meters: float = 100.0,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Finds unified land records located within radius_meters of a coordinate point [lat, lon].
    Returns matching records with exact calculated distances.
    """
    records_res = await db.execute(
        select(UnifiedLandRecord).where(
            UnifiedLandRecord.project_id == project_id,
            UnifiedLandRecord.canonical_geometry.isnot(None),
        )
    )
    records = records_res.scalars().all()

    query_point = Point(longitude, latitude)
    matches = []

    for r in records:
        geom = r.canonical_geometry
        if not geom:
            continue

        try:
            # Handle shapely geometry or WKT/dict
            if hasattr(geom, "centroid"):
                c = geom.centroid
                centroid_lat, centroid_lon = c.y, c.x
                dist_m = haversine_distance(latitude, longitude, centroid_lat, centroid_lon)
            else:
                continue

            if dist_m <= radius_meters:
                matches.append({
                    "record_id": str(r.id),
                    "record_identifier": r.record_identifier,
                    "status": r.status,
                    "distance_meters": round(dist_m, 2),
                    "canonical_area": r.area,
                    "land_use": r.canonical_attributes.get("land_use"),
                    "address": r.canonical_attributes.get("address"),
                    "centroid": [round(centroid_lat, 6), round(centroid_lon, 6)],
                })
        except Exception:
            continue

    matches.sort(key=lambda x: x["distance_meters"])
    matches = matches[:limit]

    return {
        "query_point": {"latitude": latitude, "longitude": longitude},
        "search_radius_meters": radius_meters,
        "results_count": len(matches),
        "records": matches,
    }


async def find_records_in_bbox(
    db: AsyncSession,
    project_id: uuid.UUID,
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Finds unified land records whose canonical geometry intersects the given bounding box.
    """
    search_box = box(min_lon, min_lat, max_lon, max_lat)

    records_res = await db.execute(
        select(UnifiedLandRecord).where(
            UnifiedLandRecord.project_id == project_id,
            UnifiedLandRecord.canonical_geometry.isnot(None),
        )
    )
    records = records_res.scalars().all()

    matches = []
    for r in records:
        geom = r.canonical_geometry
        if not geom:
            continue

        try:
            if hasattr(geom, "intersects") and geom.intersects(search_box):
                matches.append({
                    "record_id": str(r.id),
                    "record_identifier": r.record_identifier,
                    "status": r.status,
                    "area": r.area,
                    "land_use": r.canonical_attributes.get("land_use"),
                    "address": r.canonical_attributes.get("address"),
                })
        except Exception:
            continue

    return {
        "bounding_box": [min_lon, min_lat, max_lon, max_lat],
        "results_count": len(matches[:limit]),
        "records": matches[:limit],
    }


async def compare_feature_geometries(
    db: AsyncSession,
    project_id: uuid.UUID,
    feature_id_1: str,
    feature_id_2: str,
) -> Dict[str, Any]:
    """
    Performs pairwise spatial geometry comparison between two canonical features,
    calculating centroid distance, area delta, intersection area, and IoU overlap.
    """
    async def _resolve_feature(fid_str: str) -> Optional[CanonicalFeature]:
        try:
            val_uuid = uuid.UUID(fid_str)
            feat = await db.get(CanonicalFeature, val_uuid)
            if feat:
                return feat
        except ValueError:
            pass
        from app.models.dataset import Dataset, DatasetVersion
        stmt = (
            select(CanonicalFeature)
            .join(DatasetVersion, CanonicalFeature.dataset_version_id == DatasetVersion.id)
            .join(Dataset, DatasetVersion.dataset_id == Dataset.id)
            .where(Dataset.project_id == project_id)
        )
        res = await db.execute(stmt)
        for f in res.scalars().all():
            props = f.canonical_properties or {}
            for k, v in props.items():
                if v and str(v).lower() == fid_str.lower().strip():
                    return f
        return None

    f1_res = await _resolve_feature(feature_id_1)
    f2_res = await _resolve_feature(feature_id_2)

    if not f1_res or not f2_res:
        return {"error": "One or both canonical features were not found."}

    geom1 = f1_res.geometry
    geom2 = f2_res.geometry

    if not geom1 or not geom2:
        return {"error": "One or both features do not possess valid spatial geometries."}

    try:
        c1 = geom1.centroid
        c2 = geom2.centroid
        centroid_distance_m = haversine_distance(c1.y, c1.x, c2.y, c2.x)

        # Calculate planar intersection if valid
        intersection = geom1.intersection(geom2)
        intersection_area_deg = intersection.area if not intersection.is_empty else 0.0
        union_area_deg = geom1.union(geom2).area

        iou = (intersection_area_deg / union_area_deg) if union_area_deg > 0 else 0.0

        p1 = f1_res.canonical_properties or {}
        p2 = f2_res.canonical_properties or {}

        area1 = p1.get("area") or p1.get("sq_m")
        area2 = p2.get("area") or p2.get("sq_m")

        area_delta = None
        if area1 is not None and area2 is not None:
            try:
                area_delta = abs(float(area1) - float(area2))
            except Exception:
                pass

        return {
            "feature_1": {
                "id": str(f1_res.id),
                "type": f1_res.geometry_type,
                "reported_area": area1,
                "centroid": [round(c1.y, 6), round(c1.x, 6)],
            },
            "feature_2": {
                "id": str(f2_res.id),
                "type": f2_res.geometry_type,
                "reported_area": area2,
                "centroid": [round(c2.y, 6), round(c2.x, 6)],
            },
            "spatial_metrics": {
                "centroid_distance_meters": round(centroid_distance_m, 2),
                "intersection_over_union": round(iou, 4),
                "has_spatial_overlap": not intersection.is_empty,
                "reported_area_delta": area_delta,
            },
        }
    except Exception as e:
        return {"error": f"Failed to compute spatial comparison: {str(e)}"}
