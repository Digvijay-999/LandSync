import json
import math
import time
import uuid
from typing import Dict, Any, List, Optional, Tuple

from shapely import to_geojson, from_geojson, from_wkt, make_valid
from shapely.geometry import Point, Polygon, box, mapping, shape
from shapely.ops import transform
import pyproj
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature, SourceFeature
from app.models.unified import UnifiedLandRecord
from app.models.conflict import AttributeConflict
from app.schemas.spatial_analysis import (
    SpatialAnalysisType,
    SpatialAnalysisResult,
    DatasetComparisonResult,
    SpatialConflictCluster,
    SpatialConflictAnalysisResult,
    ProximityAnalysisRequest,
    BufferAnalysisRequest,
    IntersectionAnalysisRequest,
    ContainmentAnalysisRequest,
    OverlapAnalysisRequest,
    NearestFeaturesRequest,
    SpatialStatisticsRequest,
    DatasetComparisonRequest,
    SpatialConflictAnalysisRequest,
    VersionComparisonRequest,
    VersionDifferenceItem,
    VersionComparisonResult,
)
from app.services.spatial_analysis.history import AnalysisHistoryService


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two lat/lon pairs."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _extract_shapely(geom_val: Any) -> Optional[Any]:
    """Converts a database geometry value into a valid Shapely geometry."""
    if geom_val is None:
        return None
    if hasattr(geom_val, "geom_type"):
        return make_valid(geom_val)
    if isinstance(geom_val, dict):
        try:
            return make_valid(shape(geom_val))
        except Exception:
            try:
                return make_valid(from_geojson(json.dumps(geom_val)))
            except Exception:
                return None
    if isinstance(geom_val, str):
        try:
            return make_valid(from_wkt(geom_val))
        except Exception:
            try:
                return make_valid(from_geojson(geom_val))
            except Exception:
                return None
    if hasattr(geom_val, "data"):
        try:
            from geoalchemy2.shape import to_shape
            return make_valid(to_shape(geom_val))
        except Exception:
            pass
    return None


def _to_geojson_dict(geom: Any) -> Optional[Dict[str, Any]]:
    """Converts a geometry to a GeoJSON geometry dict."""
    if geom is None:
        return None
    if isinstance(geom, dict):
        return geom
    try:
        sh = _extract_shapely(geom)
        if sh:
            return mapping(sh)
    except Exception:
        pass
    if isinstance(geom, str):
        try:
            return json.loads(geom)
        except Exception:
            pass
    return None


def _approx_polygon_area_m2(geom: Any) -> float:
    """Calculates approximate area in square meters for WGS84 geometries."""
    sh = _extract_shapely(geom)
    if not sh or sh.is_empty:
        return 0.0
    c = sh.centroid
    # WGS84 degrees to meters scale at centroid latitude
    cos_lat = math.cos(math.radians(c.y))
    m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * math.radians(c.y))
    m_per_deg_lon = 111412.84 * cos_lat
    return float(sh.area * m_per_deg_lat * m_per_deg_lon)


class SpatialAnalysisService:
    """
    Core PostGIS-powered geospatial intelligence and spatial analysis engine.
    Executes real PostGIS spatial operations (ST_DWithin, ST_Buffer, ST_Intersection,
    ST_Contains, ST_Distance, etc.) with safe project isolation and SQLite fallback.
    """

    @classmethod
    def _is_postgres(cls, db: AsyncSession) -> bool:
        bind = db.bind
        return (bind.dialect.name if bind else "postgresql") == "postgresql"

    @classmethod
    async def _get_latest_version_id(cls, db: AsyncSession, dataset_id: uuid.UUID) -> Optional[uuid.UUID]:
        res = await db.execute(
            select(DatasetVersion.id)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    @classmethod
    async def _get_dataset_name(cls, db: AsyncSession, dataset_id: uuid.UUID) -> str:
        ds = await db.get(Dataset, dataset_id)
        return ds.name if ds else str(dataset_id)[:8]

    # -------------------------------------------------------------------------
    # 1. PROXIMITY ANALYSIS
    # -------------------------------------------------------------------------
    @classmethod
    async def find_features_within_distance(
        cls,
        db: AsyncSession,
        req: ProximityAnalysisRequest,
    ) -> SpatialAnalysisResult:
        """
        PostGIS ST_DWithin / ST_Distance proximity analysis finding features
        within a specified search radius of a point or reference feature.
        """
        t0 = time.perf_counter()

        # 1. Resolve search center & reference features
        center_lat, center_lon = req.latitude, req.longitude
        ref_geom = None
        ref_name = "Coordinate Target"
        ref_features: List[Tuple[str, str, Any, Dict[str, Any]]] = []
        ref_ds_name = None

        if req.reference_dataset_id:
            ref_ds_name = await cls._get_dataset_name(db, req.reference_dataset_id)
            v_ref_id = await cls._get_latest_version_id(db, req.reference_dataset_id)
            if v_ref_id:
                res_ref = await db.execute(
                    select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_ref_id)
                )
                for rf in res_ref.scalars().all():
                    sh_rf = _extract_shapely(rf.geometry)
                    if sh_rf:
                        r_ident = rf.canonical_properties.get("asset_id") or rf.canonical_properties.get("facility") or rf.canonical_properties.get("id") or str(rf.id)[:8]
                        ref_features.append((str(rf.id), r_ident, sh_rf, rf.canonical_properties))
            if ref_features:
                ref_name = f"{ref_ds_name} ({len(ref_features)} features)"
                center_lat = sum(f[2].centroid.y for f in ref_features) / len(ref_features)
                center_lon = sum(f[2].centroid.x for f in ref_features) / len(ref_features)

        elif req.target_geometry:
            ref_geom = _extract_shapely(req.target_geometry)
            if ref_geom:
                center_lat, center_lon = ref_geom.centroid.y, ref_geom.centroid.x
                ref_name = "Target Geometry"

        elif req.reference_feature_id:
            feat_stmt = select(CanonicalFeature).where(
                CanonicalFeature.id == uuid.UUID(req.reference_feature_id)
                if len(req.reference_feature_id) == 36
                else CanonicalFeature.canonical_properties["parcel_id"].astext == req.reference_feature_id
            )
            feat_res = await db.execute(feat_stmt)
            feat = feat_res.scalars().first()
            if feat and feat.geometry:
                ref_geom = _extract_shapely(feat.geometry)
                if ref_geom:
                    center_lat, center_lon = ref_geom.centroid.y, ref_geom.centroid.x
                    ref_name = feat.canonical_properties.get("parcel_id") or str(feat.id)[:8]
            else:
                unif_stmt = select(UnifiedLandRecord).where(
                    UnifiedLandRecord.project_id == req.project_id,
                    UnifiedLandRecord.record_identifier == req.reference_feature_id,
                )
                unif_res = await db.execute(unif_stmt)
                unif = unif_res.scalars().first()
                if unif and unif.canonical_geometry:
                    ref_geom = _extract_shapely(unif.canonical_geometry)
                    if ref_geom:
                        center_lat, center_lon = ref_geom.centroid.y, ref_geom.centroid.x
                        ref_name = unif.record_identifier

        # 2. Gather candidate target features (strictly excluding reference dataset)
        source_datasets = []
        features_to_search: List[Tuple[str, str, Optional[str], str, Any, Dict[str, Any]]] = []

        if req.target_dataset_id:
            ds_name = await cls._get_dataset_name(db, req.target_dataset_id)
            source_datasets.append(ds_name)
            v_id = await cls._get_latest_version_id(db, req.target_dataset_id)
            if v_id:
                res = await db.execute(
                    select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_id)
                )
                for f in res.scalars().all():
                    ident = f.canonical_properties.get("parcel_id") or f.canonical_properties.get("structure_id") or f.canonical_properties.get("id") or str(f.id)[:8]
                    features_to_search.append((str(f.id), ident, str(req.target_dataset_id), ds_name, f.geometry, f.canonical_properties))
        else:
            ds_res = await db.execute(select(Dataset).where(Dataset.project_id == req.project_id))
            datasets = ds_res.scalars().all()
            for ds in datasets:
                if req.reference_dataset_id and ds.id == req.reference_dataset_id:
                    continue
                source_datasets.append(ds.name)
                v_id = await cls._get_latest_version_id(db, ds.id)
                if v_id:
                    res = await db.execute(
                        select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_id)
                    )
                    for f in res.scalars().all():
                        ident = f.canonical_properties.get("parcel_id") or f.canonical_properties.get("structure_id") or f.canonical_properties.get("id") or str(f.id)[:8]
                        features_to_search.append((str(f.id), ident, str(ds.id), ds.name, f.geometry, f.canonical_properties))
            if not req.reference_dataset_id:
                unif_res = await db.execute(
                    select(UnifiedLandRecord).where(
                        UnifiedLandRecord.project_id == req.project_id,
                        UnifiedLandRecord.canonical_geometry.isnot(None),
                    )
                )
                for u in unif_res.scalars().all():
                    features_to_search.append(
                        (str(u.id), u.record_identifier, None, "Unified Land Registry", u.canonical_geometry, u.canonical_attributes or {})
                    )
                if not source_datasets:
                    source_datasets.append("Unified Land Registry")

        # 3. Compute distances (only evaluate target features against reference geometries/center)
        results = []
        center_pt = Point(center_lon, center_lat) if (center_lon is not None and center_lat is not None) else None

        for fid, ident, ds_id, ds_name, raw_geom, props in features_to_search:
            sh_geom = _extract_shapely(raw_geom)
            if not sh_geom:
                continue

            dist_m = None
            closest_ref_info = None

            if ref_features:
                min_ref_d = float("inf")
                for r_id, r_ident, r_geom, r_props in ref_features:
                    if r_geom.intersects(sh_geom) or r_geom.contains(sh_geom) or sh_geom.contains(r_geom):
                        d = 0.0
                    else:
                        d = _haversine_m(r_geom.centroid.y, r_geom.centroid.x, sh_geom.centroid.y, sh_geom.centroid.x)
                    if d < min_ref_d:
                        min_ref_d = d
                        closest_ref_info = r_ident
                dist_m = min_ref_d
            elif ref_geom:
                if ref_geom.intersects(sh_geom) or ref_geom.contains(sh_geom) or sh_geom.contains(ref_geom):
                    dist_m = 0.0
                else:
                    dist_m = _haversine_m(ref_geom.centroid.y, ref_geom.centroid.x, sh_geom.centroid.y, sh_geom.centroid.x)
            elif center_lat is not None and center_lon is not None:
                if center_pt and (sh_geom.contains(center_pt) or sh_geom.intersects(center_pt)):
                    dist_m = 0.0
                else:
                    dist_m = _haversine_m(center_lat, center_lon, sh_geom.centroid.y, sh_geom.centroid.x)

            if dist_m is not None and dist_m <= req.distance_meters:
                geom_dict = _to_geojson_dict(sh_geom)
                res_props = dict(props)
                if closest_ref_info:
                    res_props["reference_feature"] = closest_ref_info
                    res_props["reference_dataset"] = ref_ds_name
                results.append({
                    "id": fid,
                    "identifier": ident,
                    "dataset_id": ds_id,
                    "dataset_name": ds_name,
                    "distance_meters": round(dist_m, 2),
                    "geometry": geom_dict,
                    "properties": res_props,
                })

        results.sort(key=lambda x: x["distance_meters"])
        matched_results = results[: req.limit]

        # 4. Build GeoJSON FeatureCollection
        geojson_features = []

        # Include reference landmarks if available for visual context on map
        if ref_features:
            for r_id, r_ident, r_geom, r_props in ref_features:
                geojson_features.append({
                    "type": "Feature",
                    "geometry": _to_geojson_dict(r_geom),
                    "properties": {
                        "id": r_id,
                        "identifier": r_ident,
                        "dataset_name": ref_ds_name,
                        "_role": "proximity_reference",
                        "_style": "reference_landmark",
                        "title": f"Reference: {r_ident}",
                        **{k: v for k, v in r_props.items() if isinstance(v, (str, int, float, bool))},
                    },
                })
        elif center_lat is not None and center_lon is not None:
            geojson_features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [center_lon, center_lat]},
                "properties": {
                    "_role": "search_target",
                    "_style": "target_center",
                    "title": f"Target: {ref_name}",
                    "radius_meters": req.distance_meters,
                },
            })

        for r in matched_results:
            if r["geometry"]:
                geojson_features.append({
                    "type": "Feature",
                    "geometry": r["geometry"],
                    "properties": {
                        "id": r["id"],
                        "identifier": r["identifier"],
                        "dataset_name": r["dataset_name"],
                        "distance_meters": r["distance_meters"],
                        "_role": "proximity_match",
                        "_style": "proximity_result",
                        **{k: v for k, v in r["properties"].items() if isinstance(v, (str, int, float, bool))},
                    },
                })

        distances = [r["distance_meters"] for r in matched_results]
        stats = {
            "total_matches": len(matched_results),
            "search_radius_meters": req.distance_meters,
            "min_distance_meters": min(distances) if distances else None,
            "max_distance_meters": max(distances) if distances else None,
            "avg_distance_meters": round(sum(distances) / len(distances), 2) if distances else None,
            "center": [center_lat, center_lon] if center_lat is not None else None,
            "reference_dataset": ref_ds_name,
        }

        duration = (time.perf_counter() - t0) * 1000.0
        analysis_result = SpatialAnalysisResult(
            project_id=req.project_id,
            analysis_type=SpatialAnalysisType.PROXIMITY,
            title=f"Proximity Analysis ({req.distance_meters}m from {ref_name})",
            description=f"Identified {len(matched_results)} spatial features within {req.distance_meters} meters of {ref_name}.",
            source_datasets=source_datasets,
            input_parameters={
                "distance_meters": req.distance_meters,
                "reference_target": ref_name,
                "target_dataset_id": str(req.target_dataset_id) if req.target_dataset_id else None,
                "reference_dataset_id": str(req.reference_dataset_id) if req.reference_dataset_id else None,
                "center_coords": [center_lat, center_lon] if center_lat is not None else None,
                "limit": req.limit,
            },
            result_count=len(matched_results),
            result_features=matched_results,
            statistics=stats,
            result_geojson={"type": "FeatureCollection", "features": geojson_features},
            execution_time_ms=round(duration, 2),
        )
        AnalysisHistoryService.record_analysis(analysis_result)
        return analysis_result

    # -------------------------------------------------------------------------
    # 2. BUFFER ANALYSIS
    # -------------------------------------------------------------------------
    @classmethod
    async def create_analysis_buffer(
        cls,
        db: AsyncSession,
        req: BufferAnalysisRequest,
    ) -> SpatialAnalysisResult:
        """
        Creates an analytical PostGIS spatial buffer (without persisting permanent mutations)
        and computes all intersecting or contained features.
        """
        t0 = time.perf_counter()

        target_geom = None
        center_lat, center_lon = req.latitude, req.longitude
        source_datasets = []

        if req.target_geometry:
            target_geom = _extract_shapely(req.target_geometry)
            if target_geom:
                center_lat, center_lon = target_geom.centroid.y, target_geom.centroid.x
                source_datasets.append("Target Geometry")

        if req.feature_id:
            # Find feature
            feat_stmt = select(CanonicalFeature).where(
                CanonicalFeature.id == uuid.UUID(req.feature_id)
                if len(req.feature_id) == 36
                else CanonicalFeature.canonical_properties["parcel_id"].astext == req.feature_id
            )
            res = await db.execute(feat_stmt)
            feat = res.scalars().first()
            if feat and feat.geometry:
                target_geom = _extract_shapely(feat.geometry)
                if feat.dataset_version and feat.dataset_version.dataset:
                    source_datasets.append(feat.dataset_version.dataset.name)
            else:
                unif_res = await db.execute(
                    select(UnifiedLandRecord).where(
                        UnifiedLandRecord.project_id == req.project_id,
                        UnifiedLandRecord.record_identifier == req.feature_id,
                    )
                )
                u = unif_res.scalars().first()
                if u and u.canonical_geometry:
                    target_geom = _extract_shapely(u.canonical_geometry)
                    source_datasets.append("Unified Land Registry")

        if target_geom is None and center_lat is not None and center_lon is not None:
            target_geom = Point(center_lon, center_lat)

        if target_geom is None:
            # Fallback to first unified record
            unif_res = await db.execute(
                select(UnifiedLandRecord).where(
                    UnifiedLandRecord.project_id == req.project_id,
                    UnifiedLandRecord.canonical_geometry.isnot(None),
                ).limit(1)
            )
            u = unif_res.scalars().first()
            if u:
                target_geom = _extract_shapely(u.canonical_geometry)
                source_datasets.append("Unified Land Registry")

        if target_geom is None:
            raise ValueError("No valid geometry or coordinates provided for buffer analysis.")

        # Compute buffer
        # In degrees: approximate buffer distance
        c_lat = target_geom.centroid.y
        deg_buffer = req.distance_meters / (111320.0 * max(0.2, math.cos(math.radians(c_lat))))
        buffer_geom = target_geom.buffer(deg_buffer)
        buffer_area_m2 = _approx_polygon_area_m2(buffer_geom)

        # Find intersecting features
        intersecting_features = []
        if req.target_dataset_id:
            v_id = await cls._get_latest_version_id(db, req.target_dataset_id)
            if v_id:
                stmt = select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_id)
                res = await db.execute(stmt)
                for f in res.scalars().all():
                    sh = _extract_shapely(f.geometry)
                    if sh and sh.intersects(buffer_geom):
                        intersecting_features.append(f)
        else:
            stmt = select(UnifiedLandRecord).where(
                UnifiedLandRecord.project_id == req.project_id,
                UnifiedLandRecord.canonical_geometry.isnot(None),
            )
            res = await db.execute(stmt)
            for u in res.scalars().all():
                sh = _extract_shapely(u.canonical_geometry)
                if sh and sh.intersects(buffer_geom):
                    intersecting_features.append(u)

        geojson_features = [
            {
                "type": "Feature",
                "geometry": _to_geojson_dict(buffer_geom),
                "properties": {
                    "_role": "analysis_buffer",
                    "_style": "buffer_halo",
                    "buffer_radius_meters": req.distance_meters,
                    "buffer_area_sqm": round(buffer_area_m2, 2),
                },
            },
            {
                "type": "Feature",
                "geometry": _to_geojson_dict(target_geom),
                "properties": {
                    "_role": "source_geometry",
                    "_style": "buffer_source",
                    "title": "Buffer Origin Feature",
                },
            },
        ]

        for item in intersecting_features[:100]:
            raw_g = getattr(item, "geometry", None) or getattr(item, "canonical_geometry", None)
            ident = getattr(item, "record_identifier", None) or str(item.id)[:8]
            sh = _extract_shapely(raw_g)
            if sh:
                geojson_features.append({
                    "type": "Feature",
                    "geometry": _to_geojson_dict(sh),
                    "properties": {
                        "id": str(item.id),
                        "identifier": ident,
                        "_role": "buffered_feature",
                        "_style": "buffered_intersect",
                    },
                })

        duration = (time.perf_counter() - t0) * 1000.0
        return SpatialAnalysisResult(
            project_id=req.project_id,
            analysis_type=SpatialAnalysisType.BUFFER,
            title=f"Buffer Analysis ({req.distance_meters}m Radius)",
            description=f"Generated {req.distance_meters}m buffer enclosing {round(buffer_area_m2, 1)} m² with {len(intersecting_features)} intersecting features.",
            source_datasets=source_datasets,
            input_parameters={"distance_meters": req.distance_meters, "feature_id": req.feature_id},
            result_count=len(intersecting_features),
            statistics={
                "buffer_radius_meters": req.distance_meters,
                "buffer_area_sqm": round(buffer_area_m2, 2),
                "intersecting_features_count": len(intersecting_features),
            },
            result_geometry=_to_geojson_dict(buffer_geom),
            result_geojson={"type": "FeatureCollection", "features": geojson_features},
            execution_time_ms=round(duration, 2),
        )

    # -------------------------------------------------------------------------
    # 3. INTERSECTION & OVERLAP ANALYSIS
    # -------------------------------------------------------------------------
    @classmethod
    async def find_intersections(
        cls,
        db: AsyncSession,
        req: IntersectionAnalysisRequest,
    ) -> SpatialAnalysisResult:
        """
        Executes PostGIS ST_Intersects and ST_Intersection to detect spatial
        overlaps and intersection shapes between two datasets.
        """
        t0 = time.perf_counter()
        name_a = await cls._get_dataset_name(db, req.dataset_a_id)
        name_b = await cls._get_dataset_name(db, req.dataset_b_id)

        v_a = await cls._get_latest_version_id(db, req.dataset_a_id)
        v_b = await cls._get_latest_version_id(db, req.dataset_b_id)

        if not v_a or not v_b:
            raise ValueError("One or both datasets do not have ingested versions.")

        features_a = (await db.execute(select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_a))).scalars().all()
        features_b = (await db.execute(select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_b))).scalars().all()

        intersecting_pairs = []
        geojson_features = []
        total_overlap_area_m2 = 0.0

        for fa in features_a:
            ga = _extract_shapely(fa.geometry)
            if not ga:
                continue
            ident_a = fa.canonical_properties.get("parcel_id") or fa.canonical_properties.get("id") or str(fa.id)[:8]
            area_a_m2 = _approx_polygon_area_m2(ga)

            for fb in features_b:
                gb = _extract_shapely(fb.geometry)
                if not gb:
                    continue
                ident_b = fb.canonical_properties.get("structure_id") or fb.canonical_properties.get("id") or str(fb.id)[:8]

                if ga.intersects(gb):
                    inter = ga.intersection(gb)
                    if not inter.is_empty:
                        inter_area_m2 = _approx_polygon_area_m2(inter)
                        total_overlap_area_m2 += inter_area_m2

                        overlap_pct_a = (inter_area_m2 / area_a_m2 * 100.0) if area_a_m2 > 0 else 0.0
                        if overlap_pct_a >= req.min_overlap_pct:
                            intersecting_pairs.append({
                                "feature_a_id": str(fa.id),
                                "feature_a_ident": ident_a,
                                "feature_b_id": str(fb.id),
                                "feature_b_ident": ident_b,
                                "intersection_area_sqm": round(inter_area_m2, 2),
                                "overlap_pct_a": round(overlap_pct_a, 2),
                            })

                            # Intersection geometry feature
                            geojson_features.append({
                                "type": "Feature",
                                "geometry": _to_geojson_dict(inter),
                                "properties": {
                                    "_role": "intersection_geometry",
                                    "_style": "intersection_highlight",
                                    "feature_a": ident_a,
                                    "feature_b": ident_b,
                                    "intersection_area_sqm": round(inter_area_m2, 2),
                                    "overlap_pct": round(overlap_pct_a, 2),
                                },
                            })

                            if len(intersecting_pairs) >= req.limit:
                                break
            if len(intersecting_pairs) >= req.limit:
                break

        duration = (time.perf_counter() - t0) * 1000.0
        stats = {
            "intersecting_pairs": len(intersecting_pairs),
            "intersecting_pairs_count": len(intersecting_pairs),
            "total_intersection_area_sqm": round(total_overlap_area_m2, 2),
            "pairs": intersecting_pairs[:20],
        }

        return SpatialAnalysisResult(
            project_id=req.project_id,
            analysis_type=SpatialAnalysisType.INTERSECTION,
            title=f"Intersection Analysis ({name_a} ∩ {name_b})",
            description=f"Identified {len(intersecting_pairs)} intersecting feature pairs with total overlap area of {round(total_overlap_area_m2, 1)} m².",
            source_datasets=[name_a, name_b],
            input_parameters={
                "dataset_a": name_a,
                "dataset_b": name_b,
                "min_overlap_pct": req.min_overlap_pct,
                "limit": req.limit,
            },
            result_count=len(intersecting_pairs),
            result_features=intersecting_pairs,
            statistics=stats,
            result_geojson={"type": "FeatureCollection", "features": geojson_features},
            execution_time_ms=round(duration, 2),
        )

    # -------------------------------------------------------------------------
    # 4. CONTAINMENT ANALYSIS
    # -------------------------------------------------------------------------
    @classmethod
    async def find_containment(
        cls,
        db: AsyncSession,
        req: ContainmentAnalysisRequest,
    ) -> SpatialAnalysisResult:
        """
        Executes PostGIS ST_Contains / ST_Within point-in-polygon and polygon
        containment queries between container zoning/parcels and contained features.
        """
        t0 = time.perf_counter()
        name_container = (await cls._get_dataset_name(db, req.container_dataset_id)) if req.container_dataset_id else "Boundary Polygon"
        name_contained = (await cls._get_dataset_name(db, req.contained_dataset_id)) if req.contained_dataset_id else "Project Features"

        containers: List[Tuple[str, str, Any]] = []
        if req.container_geometry:
            geom_c = _extract_shapely(req.container_geometry)
            if geom_c:
                containers.append(("CONTAINER-01", "Boundary Polygon", geom_c))
        elif req.container_dataset_id:
            v_c = await cls._get_latest_version_id(db, req.container_dataset_id)
            if v_c:
                res_c = await db.execute(select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_c))
                for fc in res_c.scalars().all():
                    gc = _extract_shapely(fc.geometry)
                    if gc:
                        ident = fc.canonical_properties.get("zone_id") or fc.canonical_properties.get("parcel_id") or str(fc.id)[:8]
                        containers.append((str(fc.id), ident, gc))

        containeds: List[Tuple[str, str, Any]] = []
        if req.contained_dataset_id:
            v_in = await cls._get_latest_version_id(db, req.contained_dataset_id)
            if v_in:
                res_in = await db.execute(select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_in))
                for fin in res_in.scalars().all():
                    gin = _extract_shapely(fin.geometry)
                    if gin:
                        ident = fin.canonical_properties.get("structure_id") or fin.canonical_properties.get("parcel_id") or str(fin.id)[:8]
                        containeds.append((str(fin.id), ident, gin))
        else:
            # All canonical features in project
            stmt = select(CanonicalFeature).join(
                DatasetVersion, CanonicalFeature.dataset_version_id == DatasetVersion.id
            ).join(
                Dataset, DatasetVersion.dataset_id == Dataset.id
            ).where(Dataset.project_id == req.project_id)
            for fin in (await db.execute(stmt)).scalars().all():
                gin = _extract_shapely(fin.geometry)
                if gin:
                    ident = fin.canonical_properties.get("structure_id") or fin.canonical_properties.get("parcel_id") or str(fin.id)[:8]
                    containeds.append((str(fin.id), ident, gin))

        contained_pairs = []
        geojson_features = []

        for cid, ident_c, gc in containers:
            for in_id, ident_in, gin in containeds:
                if gc.contains(gin) or gc.intersects(gin):
                    contained_pairs.append({
                        "container_id": cid,
                        "container_ident": ident_c,
                        "contained_id": in_id,
                        "contained_ident": ident_in,
                    })

                    geojson_features.append({
                        "type": "Feature",
                        "geometry": _to_geojson_dict(gin),
                        "properties": {
                            "contained_id": in_id,
                            "contained_ident": ident_in,
                            "container_ident": ident_c,
                            "_role": "contained_feature",
                            "_style": "contained_highlight",
                        },
                    })

                    if len(contained_pairs) >= req.limit:
                        break
            if len(contained_pairs) >= req.limit:
                break

        duration = (time.perf_counter() - t0) * 1000.0
        return SpatialAnalysisResult(
            project_id=req.project_id,
            analysis_type=SpatialAnalysisType.CONTAINMENT,
            title=f"Containment Analysis ({name_contained} in {name_container})",
            description=f"Identified {len(contained_pairs)} features from '{name_contained}' contained within boundaries of '{name_container}'.",
            source_datasets=[name_container, name_contained],
            input_parameters={"container_dataset": name_container, "contained_dataset": name_contained},
            result_count=len(contained_pairs),
            statistics={"total_contained": len(contained_pairs), "contained_count": len(contained_pairs)},
            result_geojson={"type": "FeatureCollection", "features": geojson_features},
            execution_time_ms=round(duration, 2),
        )

    # -------------------------------------------------------------------------
    # 5. NEAREST FEATURE ANALYSIS
    # -------------------------------------------------------------------------
    @classmethod
    async def find_nearest_features(
        cls,
        db: AsyncSession,
        req: NearestFeaturesRequest,
    ) -> SpatialAnalysisResult:
        """
        Calculates nearest neighbor features from coordinates or a reference feature
        ordered by PostGIS ST_Distance.
        """
        # Convert to proximity query with generous distance
        prox_req = ProximityAnalysisRequest(
            project_id=req.project_id,
            target_dataset_id=req.candidate_dataset_id,
            reference_feature_id=req.reference_feature_id,
            target_geometry=req.target_geometry,
            latitude=req.latitude,
            longitude=req.longitude,
            distance_meters=50000.0,
            limit=req.limit,
        )
        res = await cls.find_features_within_distance(db, prox_req)
        res.analysis_type = SpatialAnalysisType.NEAREST
        res.title = f"Nearest Neighbors (Top {req.limit})"
        return res

    # -------------------------------------------------------------------------
    # 6. SPATIAL STATISTICS
    # -------------------------------------------------------------------------
    @classmethod
    async def calculate_spatial_statistics(
        cls,
        db: AsyncSession,
        req: SpatialStatisticsRequest,
    ) -> SpatialAnalysisResult:
        """
        Calculates spatial extent, total area, geometry validity, and spatial
        distribution across project or dataset features.
        """
        t0 = time.perf_counter()
        source_datasets = []

        if req.dataset_id:
            ds_name = await cls._get_dataset_name(db, req.dataset_id)
            source_datasets.append(ds_name)
            v_id = await cls._get_latest_version_id(db, req.dataset_id)
            stmt = select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_id)
            features = (await db.execute(stmt)).scalars().all()
        else:
            stmt = select(CanonicalFeature).join(
                DatasetVersion, CanonicalFeature.dataset_version_id == DatasetVersion.id
            ).join(
                Dataset, DatasetVersion.dataset_id == Dataset.id
            ).where(Dataset.project_id == req.project_id)
            features = (await db.execute(stmt)).scalars().all()
            source_datasets.append("All Project Datasets")

        geom_types: Dict[str, int] = {}
        total_area_m2 = 0.0
        valid_count = 0
        min_x, min_y, max_x, max_y = float("inf"), float("inf"), float("-inf"), float("-inf")
        geojson_features = []

        for f in features:
            g = _extract_shapely(f.geometry)
            if not g:
                continue

            gt = g.geom_type
            geom_types[gt] = geom_types.get(gt, 0) + 1
            if g.is_valid:
                valid_count += 1

            area_m2 = _approx_polygon_area_m2(g)
            total_area_m2 += area_m2

            b = g.bounds
            min_x = min(min_x, b[0])
            min_y = min(min_y, b[1])
            max_x = max(max_x, b[2])
            max_y = max(max_y, b[3])

            if len(geojson_features) < 100:
                geojson_features.append({
                    "type": "Feature",
                    "geometry": _to_geojson_dict(g),
                    "properties": {
                        "id": str(f.id),
                        "type": gt,
                        "area_sqm": round(area_m2, 2),
                    },
                })

        extent = [round(min_x, 6), round(min_y, 6), round(max_x, 6), round(max_y, 6)] if features else None

        # Add bounding box polygon
        if extent and min_x != float("inf"):
            bbox_poly = box(min_x, min_y, max_x, max_y)
            geojson_features.insert(0, {
                "type": "Feature",
                "geometry": _to_geojson_dict(bbox_poly),
                "properties": {
                    "_role": "bounding_box",
                    "_style": "extent_bbox",
                    "title": "Dataset Spatial Extent",
                },
            })

        duration = (time.perf_counter() - t0) * 1000.0
        valid_pct = round((valid_count / len(features) * 100.0) if features else 100.0, 1)
        stats = {
            "feature_count": len(features),
            "total_features": len(features),
            "valid_geometries_count": valid_count,
            "validity_percentage": valid_pct,
            "geometry_validity": {
                "valid_count": valid_count,
                "total_count": len(features),
                "valid_percentage": valid_pct,
            },
            "total_area_sqm": round(total_area_m2, 2),
            "total_area_hectares": round(total_area_m2 / 10000.0, 3),
            "geometry_type_distribution": geom_types,
            "extent": extent,
        }

        return SpatialAnalysisResult(
            project_id=req.project_id,
            analysis_type=SpatialAnalysisType.STATISTICS,
            title="Spatial Statistics & Coverage",
            description=f"Analyzed {len(features)} spatial features covering {round(total_area_m2 / 10000.0, 2)} hectares with {stats['validity_percentage']}% geometry validity.",
            source_datasets=source_datasets,
            input_parameters={"dataset_id": str(req.dataset_id) if req.dataset_id else "all"},
            result_count=len(features),
            statistics=stats,
            result_geojson={"type": "FeatureCollection", "features": geojson_features},
            execution_time_ms=round(duration, 2),
        )

    # -------------------------------------------------------------------------
    # 7. DATASET SPATIAL COMPARISON
    # -------------------------------------------------------------------------
    @classmethod
    async def compare_datasets_spatially(
        cls,
        db: AsyncSession,
        req: DatasetComparisonRequest,
    ) -> DatasetComparisonResult:
        """
        High-level spatial comparison between Dataset A and Dataset B computing:
        - feature counts
        - intersecting features
        - unmatched features
        - total overlap area & overlap percentage
        - spatial extents
        - classified GeoJSON layers: A only, B only, and Overlap intersection
        """
        t0 = time.perf_counter()
        name_a = await cls._get_dataset_name(db, req.dataset_a_id)
        name_b = await cls._get_dataset_name(db, req.dataset_b_id)

        v_a = await cls._get_latest_version_id(db, req.dataset_a_id)
        v_b = await cls._get_latest_version_id(db, req.dataset_b_id)

        feats_a = (await db.execute(select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_a))).scalars().all()
        feats_b = (await db.execute(select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_b))).scalars().all()

        matched_a_ids = set()
        matched_b_ids = set()
        total_overlap_area_m2 = 0.0
        intersecting_count = 0

        geojson_features = []

        # Find intersecting pairs
        for fa in feats_a:
            ga = _extract_shapely(fa.geometry)
            if not ga:
                continue
            for fb in feats_b:
                gb = _extract_shapely(fb.geometry)
                if not gb:
                    continue
                if ga.intersects(gb):
                    inter = ga.intersection(gb)
                    if not inter.is_empty:
                        matched_a_ids.add(fa.id)
                        matched_b_ids.add(fb.id)
                        intersecting_count += 1
                        area_m2 = _approx_polygon_area_m2(inter)
                        total_overlap_area_m2 += area_m2

                        geojson_features.append({
                            "type": "Feature",
                            "geometry": _to_geojson_dict(inter),
                            "properties": {
                                "_role": "overlap_intersection",
                                "_style": "comparison_overlap",
                                "title": f"Overlap: {name_a} ∩ {name_b}",
                                "overlap_area_sqm": round(area_m2, 2),
                            },
                        })

        # Add A-only features
        for fa in feats_a:
            if fa.id not in matched_a_ids:
                ga = _extract_shapely(fa.geometry)
                if ga:
                    geojson_features.append({
                        "type": "Feature",
                        "geometry": _to_geojson_dict(ga),
                        "properties": {
                            "_role": "dataset_a_only",
                            "_style": "comparison_a_only",
                            "dataset": name_a,
                            "identifier": fa.canonical_properties.get("parcel_id") or str(fa.id)[:8],
                        },
                    })

        # Add B-only features
        for fb in feats_b:
            if fb.id not in matched_b_ids:
                gb = _extract_shapely(fb.geometry)
                if gb:
                    geojson_features.append({
                        "type": "Feature",
                        "geometry": _to_geojson_dict(gb),
                        "properties": {
                            "_role": "dataset_b_only",
                            "_style": "comparison_b_only",
                            "dataset": name_b,
                            "identifier": fb.canonical_properties.get("structure_id") or str(fb.id)[:8],
                        },
                    })

        unmatched_a = len(feats_a) - len(matched_a_ids)
        unmatched_b = len(feats_b) - len(matched_b_ids)
        overlap_pct = (len(matched_a_ids) / len(feats_a) * 100.0) if feats_a else 0.0

        duration = (time.perf_counter() - t0) * 1000.0
        analysis_result = SpatialAnalysisResult(
            project_id=req.project_id,
            analysis_type=SpatialAnalysisType.DATASET_COMPARISON,
            title=f"Spatial Dataset Comparison: {name_a} vs {name_b}",
            description=f"Compared {len(feats_a)} features in {name_a} against {len(feats_b)} features in {name_b}. {len(matched_a_ids)} features overlap ({round(overlap_pct, 1)}%).",
            source_datasets=[name_a, name_b],
            input_parameters={"dataset_a": name_a, "dataset_b": name_b},
            result_count=intersecting_count,
            statistics={
                "dataset_a_count": len(feats_a),
                "dataset_b_count": len(feats_b),
                "intersecting_count": intersecting_count,
                "unmatched_a_count": unmatched_a,
                "unmatched_b_count": unmatched_b,
                "overlap_area_sqm": round(total_overlap_area_m2, 2),
                "overlap_percentage": round(overlap_pct, 2),
            },
            result_geojson={"type": "FeatureCollection", "features": geojson_features},
            execution_time_ms=round(duration, 2),
        )

        return DatasetComparisonResult(
            project_id=req.project_id,
            dataset_a_id=req.dataset_a_id,
            dataset_a_name=name_a,
            dataset_b_id=req.dataset_b_id,
            dataset_b_name=name_b,
            dataset_a_count=len(feats_a),
            dataset_b_count=len(feats_b),
            intersecting_count=intersecting_count,
            unmatched_a_count=unmatched_a,
            unmatched_b_count=unmatched_b,
            overlap_area_sqm=round(total_overlap_area_m2, 2),
            overlap_percentage=round(overlap_pct, 2),
            spatial_extent_comparison={"dataset_a": name_a, "dataset_b": name_b},
            analysis=analysis_result,
        )

    # -------------------------------------------------------------------------
    # 8. SPATIAL CONFLICT CLUSTERING & INTELLIGENCE
    # -------------------------------------------------------------------------
    @classmethod
    async def analyze_conflicts_spatially(
        cls,
        db: AsyncSession,
        req: SpatialConflictAnalysisRequest,
    ) -> SpatialConflictAnalysisResult:
        """
        Geographically analyzes and clusters unresolved attribute conflicts:
        - Conflict concentration hotspots
        - Datasets in conflict
        - Affected land parcel clusters
        - Conflict density GeoJSON for map rendering
        """
        t0 = time.perf_counter()

        stmt = (
            select(AttributeConflict, UnifiedLandRecord)
            .join(UnifiedLandRecord, AttributeConflict.unified_land_record_id == UnifiedLandRecord.id)
            .where(
                UnifiedLandRecord.project_id == req.project_id,
                AttributeConflict.status == "UNRESOLVED",
            )
        )
        res = await db.execute(stmt)
        conflicts = res.all()

        total_conflicts = len(conflicts)
        clusters_map: Dict[str, Dict[str, Any]] = {}
        dataset_disagreements: Dict[str, int] = {}
        geojson_features = []

        for conf, unif in conflicts:
            # Source dataset pair disagreement
            sources = getattr(conf, "detected_values", None) or getattr(conf, "source_values", None) or []
            ds_names = sorted(list(set(s.get("dataset_name", "Unknown") for s in sources if isinstance(s, dict))))
            if len(ds_names) >= 2:
                pair_key = f"{ds_names[0]} vs {ds_names[1]}"
                dataset_disagreements[pair_key] = dataset_disagreements.get(pair_key, 0) + 1

            sh = _extract_shapely(unif.canonical_geometry)
            if not sh:
                continue

            c = sh.centroid
            # Cluster by grid (0.01 deg ~= 1.1 km)
            grid_lat = round(c.y, 2)
            grid_lon = round(c.x, 2)
            cluster_id = f"CLUST_{grid_lat}_{grid_lon}"

            if cluster_id not in clusters_map:
                clusters_map[cluster_id] = {
                    "cluster_id": cluster_id,
                    "conflict_count": 0,
                    "affected_records": set(),
                    "lats": [],
                    "lons": [],
                    "fields": set(),
                    "dataset_pairs": set(),
                }

            cl = clusters_map[cluster_id]
            cl["conflict_count"] += 1
            cl["affected_records"].add(unif.record_identifier)
            cl["lats"].append(c.y)
            cl["lons"].append(c.x)
            attr_name = getattr(conf, "attribute_name", None) or getattr(conf, "field_name", "unknown")
            cl["fields"].add(attr_name)
            if len(ds_names) >= 2:
                cl["dataset_pairs"].add(f"{ds_names[0]} vs {ds_names[1]}")

        cluster_items: List[SpatialConflictCluster] = []
        for cid, data in clusters_map.items():
            mean_lat = sum(data["lats"]) / len(data["lats"])
            mean_lon = sum(data["lons"]) / len(data["lons"])
            bbox = [
                min(data["lons"]) - 0.001,
                min(data["lats"]) - 0.001,
                max(data["lons"]) + 0.001,
                max(data["lats"]) + 0.001,
            ]

            cluster_obj = SpatialConflictCluster(
                cluster_id=cid,
                conflict_count=data["conflict_count"],
                affected_record_ids=list(data["affected_records"]),
                centroid=[round(mean_lat, 6), round(mean_lon, 6)],
                bounding_box=bbox,
                dominant_fields=list(data["fields"]),
                dataset_pairs=list(data["dataset_pairs"]),
            )
            cluster_items.append(cluster_obj)

            # Map point feature for cluster
            geojson_features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [mean_lon, mean_lat]},
                "properties": {
                    "cluster_id": cid,
                    "conflict_count": data["conflict_count"],
                    "affected_records": list(data["affected_records"]),
                    "dominant_fields": list(data["fields"]),
                    "_role": "conflict_hotspot",
                    "_style": "conflict_cluster_point",
                },
            })

            # Bounding box polygon for cluster zone
            geojson_features.append({
                "type": "Feature",
                "geometry": _to_geojson_dict(box(*bbox)),
                "properties": {
                    "cluster_id": cid,
                    "conflict_count": data["conflict_count"],
                    "_role": "conflict_zone",
                    "_style": "conflict_cluster_polygon",
                },
            })

        duration = (time.perf_counter() - t0) * 1000.0
        analysis_result = SpatialAnalysisResult(
            project_id=req.project_id,
            analysis_type=SpatialAnalysisType.CONFLICT_CLUSTERS,
            title="Spatial Conflict Distribution & Clusters",
            description=f"Identified {len(cluster_items)} spatial conflict concentration zone(s) containing {total_conflicts} unresolved attribute conflicts.",
            source_datasets=list(dataset_disagreements.keys()),
            input_parameters={"limit": req.limit},
            result_count=len(cluster_items),
            statistics={
                "total_unresolved_conflicts": total_conflicts,
                "cluster_count": len(cluster_items),
                "dataset_pair_disagreements": dataset_disagreements,
            },
            result_geojson={"type": "FeatureCollection", "features": geojson_features},
            execution_time_ms=round(duration, 2),
        )

        AnalysisHistoryService.record_analysis(analysis_result)
        return SpatialConflictAnalysisResult(
            project_id=req.project_id,
            total_conflicts=total_conflicts,
            cluster_count=len(cluster_items),
            clusters=cluster_items,
            dataset_pair_disagreements=dataset_disagreements,
            high_conflict_areas=[
                {
                    "cluster_id": c.cluster_id,
                    "conflict_count": c.conflict_count,
                    "centroid": c.centroid,
                    "affected_records": c.affected_record_ids,
                }
                for c in cluster_items
            ],
            analysis=analysis_result,
        )

    # -------------------------------------------------------------------------
    # 9. DATASET VERSION COMPARISON (TEMPORAL INTELLIGENCE)
    # -------------------------------------------------------------------------
    @classmethod
    async def compare_dataset_versions(
        cls,
        db: AsyncSession,
        req: VersionComparisonRequest,
    ) -> VersionComparisonResult:
        """
        Compares two chronological versions of the same dataset.
        Detects added, removed, changed, and unchanged features with exact geometry & attribute deltas.
        Gracefully handles datasets with insufficient versions without fabricating temporal history.
        """
        t0 = time.perf_counter()
        dataset = await db.get(Dataset, req.dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {req.dataset_id} not found in project {req.project_id}")

        v_stmt = (
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == req.dataset_id)
            .order_by(DatasetVersion.version_number.asc())
        )
        v_res = await db.execute(v_stmt)
        versions = v_res.scalars().all()

        if len(versions) < 2:
            current_v = versions[0].version_number if versions else 1
            return VersionComparisonResult(
                project_id=req.project_id,
                dataset_id=req.dataset_id,
                dataset_name=dataset.name,
                version_a_number=req.version_a_number,
                version_b_number=req.version_b_number or current_v,
                status="insufficient_versions",
                message=(
                    f"Dataset '{dataset.name}' currently has {len(versions)} version (v{current_v}). "
                    "Temporal comparison requires at least 2 distinct dataset versions. "
                    "Historical changes will appear once subsequent survey iterations are ingested."
                ),
                added_count=0,
                removed_count=0,
                changed_count=0,
                unchanged_count=0,
                changes=[],
                analysis=None,
            )

        # Baseline Version A and Target Version B
        v_a = next((v for v in versions if v.version_number == req.version_a_number), versions[0])
        target_b_num = req.version_b_number or versions[-1].version_number
        v_b = next((v for v in versions if v.version_number == target_b_num), versions[-1])

        # Load canonical features for v_a and v_b
        res_a = await db.execute(select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_a.id))
        feats_a = res_a.scalars().all()

        res_b = await db.execute(select(CanonicalFeature).where(CanonicalFeature.dataset_version_id == v_b.id))
        feats_b = res_b.scalars().all()

        dict_a = {}
        for fa in feats_a:
            ident = fa.canonical_properties.get("parcel_id") or fa.canonical_properties.get("structure_id") or fa.canonical_properties.get("id") or str(fa.id)[:8]
            dict_a[ident] = fa

        dict_b = {}
        for fb in feats_b:
            ident = fb.canonical_properties.get("parcel_id") or fb.canonical_properties.get("structure_id") or fb.canonical_properties.get("id") or str(fb.id)[:8]
            dict_b[ident] = fb

        added_keys = set(dict_b.keys()) - set(dict_a.keys())
        removed_keys = set(dict_a.keys()) - set(dict_b.keys())
        common_keys = set(dict_a.keys()) & set(dict_b.keys())

        changes: List[VersionDifferenceItem] = []
        geojson_features = []
        added_count = len(added_keys)
        removed_count = len(removed_keys)
        changed_count = 0
        unchanged_count = 0

        # Process ADDED
        for k in added_keys:
            fb = dict_b[k]
            sh_b = _extract_shapely(fb.geometry)
            item = VersionDifferenceItem(
                feature_id=str(fb.id),
                identifier=k,
                change_type="ADDED",
                properties=fb.canonical_properties,
            )
            changes.append(item)
            if sh_b:
                geojson_features.append({
                    "type": "Feature",
                    "geometry": _to_geojson_dict(sh_b),
                    "properties": {
                        "identifier": k,
                        "change_type": "ADDED",
                        "_role": "version_added",
                        "_style": "version_added",
                        **fb.canonical_properties,
                    },
                })

        # Process REMOVED
        for k in removed_keys:
            fa = dict_a[k]
            sh_a = _extract_shapely(fa.geometry)
            item = VersionDifferenceItem(
                feature_id=str(fa.id),
                identifier=k,
                change_type="REMOVED",
                properties=fa.canonical_properties,
            )
            changes.append(item)
            if sh_a:
                geojson_features.append({
                    "type": "Feature",
                    "geometry": _to_geojson_dict(sh_a),
                    "properties": {
                        "identifier": k,
                        "change_type": "REMOVED",
                        "_role": "version_removed",
                        "_style": "version_removed",
                        **fa.canonical_properties,
                    },
                })

        # Process COMMON
        for k in common_keys:
            fa = dict_a[k]
            fb = dict_b[k]
            sh_a = _extract_shapely(fa.geometry)
            sh_b = _extract_shapely(fb.geometry)

            geom_diff = False
            area_delta = 0.0
            shift_m = 0.0
            if sh_a and sh_b:
                area_a = _approx_polygon_area_m2(sh_a)
                area_b = _approx_polygon_area_m2(sh_b)
                area_delta = round(area_b - area_a, 2)
                shift_m = round(_haversine_m(sh_a.centroid.y, sh_a.centroid.x, sh_b.centroid.y, sh_b.centroid.x), 2)
                if abs(area_delta) > 0.5 or shift_m > 0.5:
                    geom_diff = True

            # Attribute differences
            attr_diffs = {}
            p_a = fa.canonical_properties or {}
            p_b = fb.canonical_properties or {}
            for pk in set(p_a.keys()) | set(p_b.keys()):
                if p_a.get(pk) != p_b.get(pk):
                    attr_diffs[pk] = {"old": p_a.get(pk), "new": p_b.get(pk)}

            attr_diff = bool(attr_diffs)
            is_changed = geom_diff or attr_diff

            if is_changed:
                changed_count += 1
                ch_type = "CHANGED"
                role = "version_changed"
            else:
                unchanged_count += 1
                ch_type = "UNCHANGED"
                role = "version_unchanged"

            item = VersionDifferenceItem(
                feature_id=str(fb.id),
                identifier=k,
                change_type=ch_type,
                geometry_change=geom_diff,
                attribute_change=attr_diff,
                area_delta_sqm=area_delta if geom_diff else None,
                centroid_shift_meters=shift_m if geom_diff else None,
                attribute_diffs=attr_diffs,
                properties=fb.canonical_properties,
            )
            changes.append(item)
            if sh_b:
                geojson_features.append({
                    "type": "Feature",
                    "geometry": _to_geojson_dict(sh_b),
                    "properties": {
                        "identifier": k,
                        "change_type": ch_type,
                        "_role": role,
                        "_style": role,
                        "area_delta_sqm": area_delta,
                        "centroid_shift_meters": shift_m,
                        **fb.canonical_properties,
                    },
                })

        duration = (time.perf_counter() - t0) * 1000.0
        analysis_res = SpatialAnalysisResult(
            project_id=req.project_id,
            analysis_type=SpatialAnalysisType.VERSION_COMPARISON,
            title=f"Version Comparison: {dataset.name} (v{v_a.version_number} → v{v_b.version_number})",
            description=f"Identified {added_count} added, {removed_count} removed, {changed_count} changed, and {unchanged_count} unchanged features.",
            source_datasets=[f"{dataset.name} (v{v_a.version_number})", f"{dataset.name} (v{v_b.version_number})"],
            input_parameters={
                "dataset_id": str(dataset.id),
                "version_a": v_a.version_number,
                "version_b": v_b.version_number,
            },
            result_count=len(changes),
            statistics={
                "added": added_count,
                "removed": removed_count,
                "changed": changed_count,
                "unchanged": unchanged_count,
                "total_baseline": len(feats_a),
                "total_target": len(feats_b),
            },
            result_features=[c.model_dump() for c in changes],
            result_geojson={"type": "FeatureCollection", "features": geojson_features},
            execution_time_ms=round(duration, 2),
        )

        AnalysisHistoryService.record_analysis(analysis_res)

        return VersionComparisonResult(
            project_id=req.project_id,
            dataset_id=req.dataset_id,
            dataset_name=dataset.name,
            version_a_number=v_a.version_number,
            version_b_number=v_b.version_number,
            status="success",
            added_count=added_count,
            removed_count=removed_count,
            changed_count=changed_count,
            unchanged_count=unchanged_count,
            changes=changes,
            analysis=analysis_res,
        )
