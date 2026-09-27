import os
import zipfile
import json
import csv
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from app.services.ingestion.exceptions import (
    UnsupportedFormatError,
    CorruptedFileError,
    MissingShapefileComponentsError,
    MissingCoordinateColumnsError,
)


class FormatDetector:
    """
    Detects, validates, and unpacks geospatial file formats (GeoJSON, Shapefile ZIP, GeoPackage, CSV).
    Ensures safe path traversal handling and format integrity.
    """

    LAT_CANDIDATES = ["latitude", "lat", "y", "ycoord", "lat_dd", "lat_deg", "northing", "north"]
    LON_CANDIDATES = ["longitude", "long", "lon", "lng", "x", "xcoord", "lon_dd", "lon_deg", "easting", "east"]

    @classmethod
    def detect_format(cls, file_path: Path) -> Dict[str, Any]:
        """
        Inspects file extension and content to classify format and locate primary spatial data file.
        Returns a dictionary with format details and file paths.
        """
        if not file_path.exists():
            raise CorruptedFileError("File does not exist.")

        ext = file_path.suffix.lower()

        # 1. GeoJSON (.geojson or .json)
        if ext in [".geojson", ".json"]:
            return cls._validate_geojson(file_path)

        # 2. GeoPackage (.gpkg)
        if ext == ".gpkg":
            return cls._validate_geopackage(file_path)

        # 3. CSV (.csv)
        if ext == ".csv":
            return cls._validate_csv(file_path)

        # 4. Shapefile ZIP (.zip) or naked .shp (reject naked .shp with guidance to upload ZIP)
        if ext == ".zip":
            return cls._validate_and_extract_shapefile_zip(file_path)

        if ext == ".shp":
            raise UnsupportedFormatError(
                "Direct .shp upload is not supported because Shapefiles require companion files (.shx, .dbf, .prj). "
                "Please package your shapefile as a .zip archive and upload."
            )

        raise UnsupportedFormatError(
            f"Unsupported file format '{ext}'. Supported formats: GeoJSON (.geojson, .json), "
            "Shapefile (.zip containing .shp, .shx, .dbf), GeoPackage (.gpkg), and CSV with coordinates (.csv)."
        )

    @classmethod
    def _validate_geojson(cls, file_path: Path) -> Dict[str, Any]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                # Read leading bytes to check if it's JSON
                content_start = f.read(2048).strip()
                if not (content_start.startswith("{") or content_start.startswith("[")):
                    raise CorruptedFileError("File does not start with valid JSON syntax.")
            
            # Verify basic JSON parseability
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    t = data.get("type", "").lower()
                    if t not in ["featurecollection", "feature", "geometrycollection", "polygon", "multipolygon", "point", "linestring"]:
                        # Might still be GeoJSON or GeoPandas can parse
                        pass
        except json.JSONDecodeError as exc:
            raise CorruptedFileError(f"Corrupted or invalid GeoJSON file: {exc.msg}")
        except Exception as exc:
            raise CorruptedFileError(f"Unable to read GeoJSON file: {str(exc)}")

        return {
            "format": "geojson",
            "source_type": "vector",
            "main_file": file_path,
            "extract_dir": None,
            "csv_coords": None,
        }

    @classmethod
    def _validate_geopackage(cls, file_path: Path) -> Dict[str, Any]:
        # Validate SQLite header for GeoPackage
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
                if not header.startswith(b"SQLite format 3"):
                    raise CorruptedFileError("Invalid GeoPackage: File header is not a valid SQLite database.")
        except Exception as exc:
            raise CorruptedFileError(f"Unable to verify GeoPackage header: {str(exc)}")

        return {
            "format": "geopackage",
            "source_type": "vector",
            "main_file": file_path,
            "extract_dir": None,
            "csv_coords": None,
        }

    @classmethod
    def _validate_csv(cls, file_path: Path) -> Dict[str, Any]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                sample = f.read(8192)
                if not sample.strip():
                    raise CorruptedFileError("CSV file is empty.")
                
                f.seek(0)
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    raise CorruptedFileError("CSV file has no header row.")
        except Exception as exc:
            raise CorruptedFileError(f"Unable to read CSV file: {str(exc)}")

        lat_col, lon_col = cls.find_coordinate_columns(header)
        if not lat_col or not lon_col:
            columns_found = ", ".join([f"'{c}'" for c in header[:15]])
            raise MissingCoordinateColumnsError(
                f"Could not automatically identify latitude and longitude columns in CSV. "
                f"Columns detected: [{columns_found}]. Supported coordinate names include: "
                f"Latitude ({', '.join(cls.LAT_CANDIDATES)}) and Longitude ({', '.join(cls.LON_CANDIDATES)})."
            )

        return {
            "format": "csv",
            "source_type": "vector",
            "main_file": file_path,
            "extract_dir": None,
            "csv_coords": (lat_col, lon_col),
        }

    @classmethod
    def find_coordinate_columns(cls, columns: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Identifies latitude and longitude column headers case-insensitively."""
        lat_col: Optional[str] = None
        lon_col: Optional[str] = None

        col_map = {c.strip().lower(): c for c in columns if c and c.strip()}

        # Exact match candidates first
        for candidate in cls.LAT_CANDIDATES:
            if candidate in col_map:
                lat_col = col_map[candidate]
                break

        for candidate in cls.LON_CANDIDATES:
            if candidate in col_map:
                lon_col = col_map[candidate]
                break

        # Fuzzy substring match if not found
        if not lat_col:
            for clean, orig in col_map.items():
                if "lat" in clean:
                    lat_col = orig
                    break

        if not lon_col:
            for clean, orig in col_map.items():
                if any(x in clean for x in ["lon", "lng"]):
                    lon_col = orig
                    break

        return lat_col, lon_col

    @classmethod
    def _validate_and_extract_shapefile_zip(cls, zip_path: Path) -> Dict[str, Any]:
        """
        Safely extracts ZIP containing shapefile components (.shp, .shx, .dbf, optional .prj).
        Guards against Zip Slip (path traversal) attacks.
        """
        if not zipfile.is_zipfile(zip_path):
            raise CorruptedFileError("The uploaded .zip file is not a valid ZIP archive.")

        extract_dir = zip_path.parent / "extracted_shapefile"
        extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # 1. Zip slip check & list entries
                namelist = zf.namelist()
                resolved_extract_dir = extract_dir.resolve()

                for member in namelist:
                    member_path = (extract_dir / member).resolve()
                    if not str(member_path).startswith(str(resolved_extract_dir)):
                        raise CorruptedFileError(
                            f"Security validation failed: Zip entry '{member}' attempts path traversal."
                        )

                zf.extractall(extract_dir)

            # 2. Locate .shp, .shx, .dbf files
            shp_files = list(extract_dir.glob("**/*.shp"))
            if not shp_files:
                raise MissingShapefileComponentsError("Archive does not contain any .shp file.")

            main_shp = shp_files[0]
            stem = main_shp.stem
            parent = main_shp.parent

            # Check required companion files (.shx, .dbf)
            shx_file = parent / f"{stem}.shx"
            dbf_file = parent / f"{stem}.dbf"

            # Case-insensitive companion search
            all_parent_files = {p.name.lower(): p for p in parent.iterdir()}
            has_shx = f"{stem.lower()}.shx" in all_parent_files
            has_dbf = f"{stem.lower()}.dbf" in all_parent_files

            if not (has_shx and has_dbf):
                missing = []
                if not has_shx:
                    missing.append(f"{stem}.shx")
                if not has_dbf:
                    missing.append(f"{stem}.dbf")
                raise MissingShapefileComponentsError(
                    f"Incomplete Shapefile archive: missing required companion files: {', '.join(missing)}."
                )

            return {
                "format": "shapefile",
                "source_type": "vector",
                "main_file": main_shp,
                "extract_dir": extract_dir,
                "csv_coords": None,
            }

        except (MissingShapefileComponentsError, CorruptedFileError):
            raise
        except Exception as exc:
            raise CorruptedFileError(f"Failed to process Shapefile ZIP archive: {str(exc)}")
