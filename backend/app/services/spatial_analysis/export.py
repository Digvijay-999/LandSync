import csv
import io
import json
from typing import Dict, Any, List
from app.schemas.spatial_analysis import SpatialAnalysisResult


class AnalysisExportService:
    """
    Exports real spatial analysis results into client-ready GeoJSON and CSV formats.
    """

    @classmethod
    def to_geojson(cls, result: SpatialAnalysisResult) -> str:
        """Serializes full spatial analysis result as valid RFC 7946 GeoJSON."""
        payload = {
            "type": "FeatureCollection",
            "metadata": {
                "analysis_id": str(result.analysis_id),
                "project_id": str(result.project_id),
                "analysis_type": result.analysis_type.value,
                "title": result.title,
                "description": result.description,
                "source_datasets": result.source_datasets,
                "result_count": result.result_count,
                "statistics": result.statistics,
                "execution_time_ms": result.execution_time_ms,
                "created_at": result.created_at.isoformat(),
            },
            "features": result.result_geojson.get("features", []),
        }
        return json.dumps(payload, indent=2)

    @classmethod
    def to_csv(cls, result: SpatialAnalysisResult) -> str:
        """Serializes spatial analysis feature results into standard CSV."""
        output = io.StringIO()
        fieldnames = [
            "feature_id",
            "identifier",
            "dataset_name",
            "role",
            "distance_meters",
            "overlap_area_sqm",
            "overlap_pct",
            "geometry_type",
            "latitude",
            "longitude",
            "properties",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        features = result.result_geojson.get("features", [])
        if not features and result.result_features:
            for rf in result.result_features:
                geom = rf.get("geometry") or {}
                props = rf.get("properties") or {}
                writer.writerow({
                    "feature_id": rf.get("id", ""),
                    "identifier": rf.get("identifier", ""),
                    "dataset_name": rf.get("dataset_name", ""),
                    "role": "result_feature",
                    "distance_meters": rf.get("distance_meters", ""),
                    "overlap_area_sqm": rf.get("overlap_area_sqm", ""),
                    "overlap_pct": rf.get("overlap_pct", ""),
                    "geometry_type": geom.get("type", "Unknown"),
                    "latitude": "",
                    "longitude": "",
                    "properties": json.dumps(props),
                })
        else:
            for feat in features:
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates")
                lat, lon = "", ""
                if geom.get("type") == "Point" and coords and len(coords) >= 2:
                    lon, lat = coords[0], coords[1]

                writer.writerow({
                    "feature_id": props.get("id") or props.get("feature_id") or "",
                    "identifier": props.get("identifier") or props.get("title") or "",
                    "dataset_name": props.get("dataset_name") or "",
                    "role": props.get("_role") or "",
                    "distance_meters": props.get("distance_meters") or "",
                    "overlap_area_sqm": props.get("overlap_area_sqm") or "",
                    "overlap_pct": props.get("overlap_pct") or "",
                    "geometry_type": geom.get("type", "Unknown"),
                    "latitude": lat,
                    "longitude": lon,
                    "properties": json.dumps({k: v for k, v in props.items() if not k.startswith("_")}),
                })

        return output.getvalue()
