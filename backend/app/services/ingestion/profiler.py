import numpy as np
import geopandas as gpd
from typing import Dict, Any, List, Optional
from shapely.geometry.base import BaseGeometry
from app.schemas.dataset import (
    DatasetProfile,
    GeneralProfile,
    GeometryProfile,
    SpatialProfile,
    AttributeProfile,
    BoundingBox,
    DatasetField,
)


class DatasetProfiler:
    """
    Computes comprehensive structural, spatial, geometric, and attribute profiles
    for ingested GeoDataFrames.
    """

    @classmethod
    def profile(
        cls,
        gdf: gpd.GeoDataFrame,
        filename: str,
        source_format: str,
        file_size: int,
    ) -> DatasetProfile:
        feature_count = len(gdf)

        # 1. Geometry Analysis
        geom_profile = cls._profile_geometry(gdf)

        # 2. Spatial & CRS Analysis
        spatial_profile = cls._profile_spatial(gdf)

        # 3. Attribute Analysis
        attr_profile = cls._profile_attributes(gdf)

        # 4. General Profile
        general_profile = GeneralProfile(
            filename=filename,
            format=source_format,
            file_size=file_size,
            feature_count=feature_count,
        )

        return DatasetProfile(
            general=general_profile,
            geometry=geom_profile,
            spatial=spatial_profile,
            attributes=attr_profile,
        )

    @classmethod
    def _profile_geometry(cls, gdf: gpd.GeoDataFrame) -> GeometryProfile:
        geom_col = gdf.geometry
        total = len(gdf)

        type_dist: Dict[str, int] = {}
        empty_count = 0
        valid_count = 0
        invalid_count = 0

        for geom in geom_col:
            if geom is None or (isinstance(geom, BaseGeometry) and geom.is_empty):
                empty_count += 1
                type_dist["Empty/None"] = type_dist.get("Empty/None", 0) + 1
            elif isinstance(geom, BaseGeometry):
                gtype = geom.geom_type
                type_dist[gtype] = type_dist.get(gtype, 0) + 1

                if geom.is_valid:
                    valid_count += 1
                else:
                    invalid_count += 1
            else:
                empty_count += 1
                type_dist["Unknown"] = type_dist.get("Unknown", 0) + 1

        # Determine dominant geometry type
        non_empty_dist = {k: v for k, v in type_dist.items() if k not in ["Empty/None", "Unknown"]}
        if not non_empty_dist:
            dominant_type = "None"
        elif len(non_empty_dist) == 1:
            dominant_type = next(iter(non_empty_dist.keys()))
        else:
            # Check if one type constitutes >80% or classify as Mixed
            sorted_types = sorted(non_empty_dist.items(), key=lambda x: x[1], reverse=True)
            if sorted_types[0][1] / max(1, total - empty_count) >= 0.8:
                dominant_type = sorted_types[0][0]
            else:
                dominant_type = "Mixed"

        validity_pct = round((valid_count / total * 100.0) if total > 0 else 0.0, 2)

        return GeometryProfile(
            geometry_type=dominant_type,
            geometry_type_distribution=type_dist,
            geometry_count=total,
            valid_geometry_count=valid_count,
            invalid_geometry_count=invalid_count,
            empty_geometry_count=empty_count,
            validity_percentage=validity_pct,
        )

    @classmethod
    def _profile_spatial(cls, gdf: gpd.GeoDataFrame) -> SpatialProfile:
        crs_str: Optional[str] = None
        crs_name: Optional[str] = None
        is_geographic: Optional[bool] = None
        bbox: Optional[BoundingBox] = None

        if gdf.crs is not None:
            # Detect EPSG authority code
            epsg = gdf.crs.to_epsg()
            if epsg:
                crs_str = f"EPSG:{epsg}"
            else:
                crs_str = gdf.crs.to_string()

            crs_name = getattr(gdf.crs, "name", None) or crs_str
            is_geographic = getattr(gdf.crs, "is_geographic", False)

        # Bounding Box calculation
        try:
            bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
            if bounds is not None and len(bounds) == 4 and not np.isnan(bounds).any():
                bbox = BoundingBox(
                    min_x=round(float(bounds[0]), 6),
                    min_y=round(float(bounds[1]), 6),
                    max_x=round(float(bounds[2]), 6),
                    max_y=round(float(bounds[3]), 6),
                )
        except Exception:
            bbox = None

        return SpatialProfile(
            crs=crs_str,
            crs_name=crs_name,
            is_geographic=is_geographic,
            bounds=bbox,
        )

    @classmethod
    def _profile_attributes(cls, gdf: gpd.GeoDataFrame) -> AttributeProfile:
        fields: List[DatasetField] = []
        geom_name = gdf.geometry.name if hasattr(gdf, "geometry") else "geometry"

        for col in gdf.columns:
            if col == geom_name:
                continue

            series = gdf[col]
            dtype_name = str(series.dtype)

            # Map common pandas/numpy types to clean representations
            if "int" in dtype_name:
                clean_type = "Integer"
            elif "float" in dtype_name:
                clean_type = "Float"
            elif "bool" in dtype_name:
                clean_type = "Boolean"
            elif "datetime" in dtype_name:
                clean_type = "DateTime"
            else:
                clean_type = "String"

            null_count = int(series.isna().sum())
            try:
                # Calculate unique count safely
                unique_count = int(series.nunique(dropna=True))
            except Exception:
                unique_count = 0

            fields.append(
                DatasetField(
                    name=str(col),
                    data_type=clean_type,
                    null_count=null_count,
                    unique_count=unique_count,
                )
            )

        return AttributeProfile(
            field_count=len(fields),
            fields=fields,
        )
