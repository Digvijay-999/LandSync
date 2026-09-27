import pyproj
from typing import Optional, Dict, Any
import shapely
from shapely.geometry.base import BaseGeometry
from shapely.geometry import shape, mapping
from shapely.ops import transform


class CRSError(Exception):
    """Base exception for coordinate reference system operations."""
    def __init__(self, message: str, code: str = "CRS_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class MissingCRSError(CRSError):
    """Raised when source or target CRS is missing and cannot be inferred."""
    def __init__(self, message: str = "Dataset CRS is missing. Specify an authoritative source CRS before canonicalization."):
        super().__init__(message, code="MISSING_CRS")


class InvalidCRSError(CRSError):
    """Raised when a CRS identifier cannot be parsed or resolved."""
    def __init__(self, message: str):
        super().__init__(message, code="INVALID_CRS")


class TransformationError(CRSError):
    """Raised when geometric coordinates cannot be transformed between CRS."""
    def __init__(self, message: str):
        super().__init__(message, code="TRANSFORMATION_FAILED")


class CRSNormalizer:
    """
    Authoritative Coordinate Reference System (CRS) validation,
    normalization, and coordinate reprojection service.
    Uses PyProj and Shapely with strict axis ordering (always_xy=True).
    """

    @classmethod
    def parse_crs(cls, crs_str: Optional[str]) -> pyproj.CRS:
        """
        Parses and validates a CRS string into a pyproj.CRS instance.
        """
        if not crs_str or not str(crs_str).strip():
            raise MissingCRSError("Coordinate reference system (CRS) identifier is required.")

        clean_str = str(crs_str).strip()
        try:
            return pyproj.CRS.from_user_input(clean_str)
        except Exception as exc:
            raise InvalidCRSError(
                f"Failed to resolve coordinate reference system '{clean_str}': {str(exc)}. "
                "Ensure valid EPSG code (e.g. 'EPSG:4326', 'EPSG:3857') or Proj string."
            )

    @classmethod
    def normalize_crs_code(cls, crs_str: Optional[str]) -> str:
        """
        Returns a standardized CRS authority string such as 'EPSG:4326'.
        """
        crs_obj = cls.parse_crs(crs_str)
        epsg = crs_obj.to_epsg()
        if epsg:
            return f"EPSG:{epsg}"
        return crs_obj.to_string()

    @classmethod
    def get_srid(cls, crs_str: Optional[str]) -> int:
        """
        Extracts the integer SRID for PostGIS geometry storage.
        Defaults to 4326 if not specifically resolvable.
        """
        if not crs_str:
            return 4326
        try:
            crs_obj = cls.parse_crs(crs_str)
            epsg = crs_obj.to_epsg()
            return int(epsg) if epsg else 4326
        except Exception:
            return 4326

    # Aliases for convenience
    normalize_crs_string = normalize_crs_code
    to_srid = get_srid

    @classmethod
    def transform_geometry(
        cls,
        geom: BaseGeometry,
        source_crs_str: str,
        target_crs_str: str,
    ) -> BaseGeometry:
        """
        Transforms a Shapely geometry from source_crs to target_crs.
        Ensures consistent (x, y) / (lon, lat) axis order via always_xy=True.
        """
        if geom is None or geom.is_empty:
            return geom

        source_crs = cls.parse_crs(source_crs_str)
        target_crs = cls.parse_crs(target_crs_str)

        # Skip transformation if CRSs are equivalent
        if source_crs == target_crs:
            return geom

        try:
            transformer = pyproj.Transformer.from_crs(
                source_crs,
                target_crs,
                always_xy=True,
            )
            transformed = transform(transformer.transform, geom)
            return transformed
        except Exception as exc:
            raise TransformationError(
                f"Failed to transform geometry from {source_crs.to_string()} to {target_crs.to_string()}: {str(exc)}"
            )

    @classmethod
    def to_geojson(cls, geom: BaseGeometry) -> Dict[str, Any]:
        """Converts Shapely geometry to GeoJSON dict."""
        return mapping(geom)

    @classmethod
    def from_geojson(cls, geom_dict: Dict[str, Any]) -> BaseGeometry:
        """Converts GeoJSON dict to Shapely geometry."""
        return shape(geom_dict)
