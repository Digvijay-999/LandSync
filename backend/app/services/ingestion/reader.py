import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path
from typing import Dict, Any, Optional
from app.services.ingestion.exceptions import (
    CorruptedFileError,
    EmptyDatasetError,
    InvalidCoordinateError,
)
from app.services.crs.normalizer import CRSNormalizer, MissingCRSError, InvalidCRSError


class DatasetReader:
    """
    Reads vector datasets into unified GeoPandas GeoDataFrames across all supported formats.
    """

    @classmethod
    def read_dataset(
        cls,
        format_info: Dict[str, Any],
        custom_crs: Optional[str] = None,
    ) -> gpd.GeoDataFrame:
        """
        Loads the spatial dataset into a GeoPandas GeoDataFrame.
        """
        fmt = format_info["format"]
        main_file: Path = format_info["main_file"]

        try:
            if fmt == "csv":
                gdf = cls._read_csv(format_info, custom_crs=custom_crs)
            else:
                # GeoJSON, Shapefile (.shp), GeoPackage (.gpkg)
                gdf = gpd.read_file(str(main_file))

                # If custom_crs is supplied, validate and assign
                if custom_crs:
                    CRSNormalizer.parse_crs(custom_crs)
                    gdf = gdf.set_crs(custom_crs, allow_override=True)
                elif fmt == "geojson" and gdf.crs is None:
                    # RFC 7946 GeoJSON defaults to EPSG:4326
                    gdf = gdf.set_crs("EPSG:4326")

        except (EmptyDatasetError, InvalidCoordinateError, MissingCRSError, InvalidCRSError):
            raise
        except Exception as exc:
            raise CorruptedFileError(f"Failed to parse geospatial data using GeoPandas/GDAL: {str(exc)}")

        if gdf is None or gdf.empty or len(gdf) == 0:
            raise EmptyDatasetError("Dataset contains no valid spatial features.")

        return gdf

    @classmethod
    def _read_csv(
        cls,
        format_info: Dict[str, Any],
        custom_crs: Optional[str] = None,
    ) -> gpd.GeoDataFrame:
        """
        Parses CSV, validates coordinate columns, creates Point geometries, and constructs GeoDataFrame.
        """
        main_file: Path = format_info["main_file"]
        lat_col, lon_col = format_info["csv_coords"]

        try:
            df = pd.read_csv(main_file)
        except Exception as exc:
            raise CorruptedFileError(f"Error parsing CSV file: {str(exc)}")

        if df is None or df.empty or len(df) == 0:
            raise EmptyDatasetError("Dataset contains no valid spatial features.")

        # Ensure coordinate columns exist
        if lat_col not in df.columns or lon_col not in df.columns:
            raise InvalidCoordinateError(f"Coordinate columns '{lat_col}' and '{lon_col}' not found in CSV.")

        # Convert coordinates to numeric, converting invalid strings to NaN
        df["_lat_clean"] = pd.to_numeric(df[lat_col], errors="coerce")
        df["_lon_clean"] = pd.to_numeric(df[lon_col], errors="coerce")

        valid_coord_mask = df["_lat_clean"].notna() & df["_lon_clean"].notna()
        valid_coords_count = int(valid_coord_mask.sum())

        if valid_coords_count == 0:
            raise InvalidCoordinateError(
                f"No valid numeric coordinates found in columns '{lat_col}' and '{lon_col}'."
            )

        # Build point geometries for valid rows, None for invalid
        geometry = [
            Point(xy) if pd.notna(xy[0]) and pd.notna(xy[1]) else None
            for xy in zip(df["_lon_clean"], df["_lat_clean"])
        ]

        # Determine CRS for CSV
        # If user specified CRS, use it; otherwise check if values look like WGS84 lat/lon
        assigned_crs = custom_crs
        if not assigned_crs:
            min_lat = df["_lat_clean"].min()
            max_lat = df["_lat_clean"].max()
            min_lon = df["_lon_clean"].min()
            max_lon = df["_lon_clean"].max()

            # Geographic bounds check (-90 to 90 lat, -180 to 180 lon)
            if -90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0 and -180.0 <= min_lon <= 180.0 and -180.0 <= max_lon <= 180.0:
                assigned_crs = "EPSG:4326"
            else:
                # Outside typical geographic range - still assign default but record in metadata
                assigned_crs = "EPSG:4326"

        # Drop temporary cleanup columns
        df = df.drop(columns=["_lat_clean", "_lon_clean"])

        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=assigned_crs)
        return gdf
