import math
import re
from typing import Optional, Dict, Any, Tuple, List
from shapely.geometry.base import BaseGeometry
from shapely.geometry import Polygon, MultiPolygon, Point, MultiPoint, LineString, MultiLineString
from shapely.ops import transform
from shapely import make_valid
from app.services.dataset import extract_shapely_geom


def haversine_distance_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Computes accurate great-circle geodesic distance in meters between two (lon, lat) points in degrees.
    """
    R = 6371000.0  # Mean radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def compute_centroid_distance_meters(geom1: BaseGeometry, geom2: BaseGeometry) -> float:
    """
    Computes the distance between two geometry centroids in meters.
    Automatically detects whether coordinates are geographic (WGS84 degrees) or projected (meters).
    """
    c1 = geom1.centroid
    c2 = geom2.centroid

    # Check if coordinates are geographic (degrees)
    if -180.0 <= c1.x <= 180.0 and -90.0 <= c1.y <= 90.0 and -180.0 <= c2.x <= 180.0 and -90.0 <= c2.y <= 90.0:
        return haversine_distance_meters(c1.x, c1.y, c2.x, c2.y)
    
    # Otherwise Euclidean distance in projected meters
    return math.hypot(c2.x - c1.x, c2.y - c1.y)


class MatchingSignals:
    """
    Computes individual, normalized (0.0 to 1.0) explainable matching signals
    between two canonical features.
    """

    @staticmethod
    def spatial_overlap(geom_a: Any, geom_b: Any) -> Optional[float]:
        """
        Calculates normalized spatial overlap for polygonal geometries:
        Intersection area / Union area (IoU).
        Returns None (not applicable) for non-polygonal geometries.
        """
        sh_a = extract_shapely_geom(geom_a)
        sh_b = extract_shapely_geom(geom_b)

        if sh_a is None or sh_b is None or sh_a.is_empty or sh_b.is_empty:
            return 0.0

        # Only polygonal geometries support areal overlap
        if not (isinstance(sh_a, (Polygon, MultiPolygon)) and isinstance(sh_b, (Polygon, MultiPolygon))):
            return None

        # Clean geometries to ensure validity
        if not sh_a.is_valid:
            sh_a = make_valid(sh_a)
        if not sh_b.is_valid:
            sh_b = make_valid(sh_b)

        union_geom = sh_a.union(sh_b)
        union_area = union_geom.area if union_geom is not None and not union_geom.is_empty else 0.0
        if union_area <= 0.0:
            return 0.0

        intersection_geom = sh_a.intersection(sh_b)
        intersection_area = intersection_geom.area if intersection_geom is not None and not intersection_geom.is_empty else 0.0

        return max(0.0, min(1.0, float(intersection_area / union_area)))

    @staticmethod
    def centroid_distance(geom_a: Any, geom_b: Any, max_distance_meters: float = 50.0) -> float:
        """
        Calculates centroid proximity normalized to 0.0 - 1.0:
        1.0 = exact same location, 0.0 = distance >= max_distance_meters.
        """
        sh_a = extract_shapely_geom(geom_a)
        sh_b = extract_shapely_geom(geom_b)

        if sh_a is None or sh_b is None or sh_a.is_empty or sh_b.is_empty:
            return 0.0

        dist_m = compute_centroid_distance_meters(sh_a, sh_b)
        if dist_m >= max_distance_meters:
            return 0.0

        return max(0.0, min(1.0, float(1.0 - (dist_m / max_distance_meters))))

    @staticmethod
    def area_similarity(geom_a: Any, geom_b: Any) -> Optional[float]:
        """
        Calculates normalized area similarity for polygons:
        min(area_a, area_b) / max(area_a, area_b).
        Returns None for non-polygonal geometries.
        """
        sh_a = extract_shapely_geom(geom_a)
        sh_b = extract_shapely_geom(geom_b)

        if sh_a is None or sh_b is None or sh_a.is_empty or sh_b.is_empty:
            return 0.0

        if not (isinstance(sh_a, (Polygon, MultiPolygon)) and isinstance(sh_b, (Polygon, MultiPolygon))):
            return None

        area_a = abs(sh_a.area)
        area_b = abs(sh_b.area)
        max_area = max(area_a, area_b)

        if max_area <= 0.0:
            return 0.0

        return max(0.0, min(1.0, float(min(area_a, area_b) / max_area)))

    @staticmethod
    def geometry_similarity(geom_a: Any, geom_b: Any, max_distance_meters: float = 50.0) -> float:
        """
        Calculates geometry shape and topological similarity (0.0 to 1.0).
        - Polygon vs Polygon: IoU shape similarity.
        - Point vs Point: Proximity score.
        - Point vs Polygon: Containment score (1.0 if contained, proximity to boundary otherwise).
        - LineString: Normalized buffer overlap / distance.
        """
        sh_a = extract_shapely_geom(geom_a)
        sh_b = extract_shapely_geom(geom_b)

        if sh_a is None or sh_b is None or sh_a.is_empty or sh_b.is_empty:
            return 0.0

        # Polygon vs Polygon
        if isinstance(sh_a, (Polygon, MultiPolygon)) and isinstance(sh_b, (Polygon, MultiPolygon)):
            overlap = MatchingSignals.spatial_overlap(sh_a, sh_b)
            return overlap if overlap is not None else 0.0

        # Point vs Point
        if isinstance(sh_a, (Point, MultiPoint)) and isinstance(sh_b, (Point, MultiPoint)):
            return MatchingSignals.centroid_distance(sh_a, sh_b, max_distance_meters)

        # Point vs Polygon
        if isinstance(sh_a, (Point, MultiPoint)) and isinstance(sh_b, (Polygon, MultiPolygon)):
            pt = sh_a.centroid if isinstance(sh_a, MultiPoint) else sh_a
            if sh_b.contains(pt):
                return 1.0
            dist_m = compute_centroid_distance_meters(pt, sh_b.exterior if hasattr(sh_b, 'exterior') else sh_b)
            return max(0.0, min(1.0, 1.0 - (dist_m / max_distance_meters)))

        if isinstance(sh_b, (Point, MultiPoint)) and isinstance(sh_a, (Polygon, MultiPolygon)):
            pt = sh_b.centroid if isinstance(sh_b, MultiPoint) else sh_b
            if sh_a.contains(pt):
                return 1.0
            dist_m = compute_centroid_distance_meters(pt, sh_a.exterior if hasattr(sh_a, 'exterior') else sh_a)
            return max(0.0, min(1.0, 1.0 - (dist_m / max_distance_meters)))

        # Default fallback: centroid distance
        return MatchingSignals.centroid_distance(sh_a, sh_b, max_distance_meters)

    @staticmethod
    def attribute_similarity(
        props_a: Dict[str, Any],
        props_b: Dict[str, Any],
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Compares attributes between two features using schema-agnostic field normalization.
        Returns (normalized_score, explanation_dict).
        """
        clean_a = {k: v for k, v in props_a.items() if not k.startswith('_') and v is not None}
        clean_b = {k: v for k, v in props_b.items() if not k.startswith('_') and v is not None}

        if not clean_a or not clean_b:
            return 0.5, {"matched_fields": [], "note": "Insufficient attribute data"}

        # Define semantic field categories for cross-schema alignment
        SEMANTIC_GROUPS = {
            "identifier": [
                "id", "fid", "parcel_id", "parcel_no", "plot_no", "survey_no",
                "property_id", "code", "asset_id", "structure_id", "building_id",
            ],
            "name": [
                "name", "owner", "owner_name", "label", "asset_name", "facility_name",
                "structure_name", "title", "description",
            ],
            "type": [
                "type", "use", "land_use", "class", "category", "facility_type",
                "structure_type", "asset_type", "status",
            ],
            "metric": [
                "area", "area_sqm", "sqm", "sqft", "floors", "height", "units",
            ],
        }

        def normalize_key(key: str) -> str:
            return re.sub(r"[^a-z0-9]", "", key.lower())

        norm_a = {normalize_key(k): (k, v) for k, v in clean_a.items()}
        norm_b = {normalize_key(k): (k, v) for k, v in clean_b.items()}

        field_matches: List[Dict[str, Any]] = []
        scores: List[float] = []

        # 1. Check exact key matches
        common_keys = set(norm_a.keys()).intersection(set(norm_b.keys()))
        for k in common_keys:
            orig_k_a, val_a = norm_a[k]
            orig_k_b, val_b = norm_b[k]
            score, sim_type = MatchingSignals._compare_values(val_a, val_b)
            scores.append(score)
            field_matches.append({
                "field_a": orig_k_a,
                "field_b": orig_k_b,
                "value_a": str(val_a),
                "value_b": str(val_b),
                "similarity": round(score, 3),
                "type": sim_type,
            })

        # 2. Check semantic group alignments for unmapped keys
        matched_a_keys = {m["field_a"] for m in field_matches}
        matched_b_keys = {m["field_b"] for m in field_matches}

        for group_name, candidate_keys in SEMANTIC_GROUPS.items():
            norm_candidates = [normalize_key(ck) for ck in candidate_keys]
            found_a = [norm_a[k] for k in norm_candidates if k in norm_a and norm_a[k][0] not in matched_a_keys]
            found_b = [norm_b[k] for k in norm_candidates if k in norm_b and norm_b[k][0] not in matched_b_keys]

            if found_a and found_b:
                orig_k_a, val_a = found_a[0]
                orig_k_b, val_b = found_b[0]
                score, sim_type = MatchingSignals._compare_values(val_a, val_b)
                scores.append(score)
                field_matches.append({
                    "field_a": orig_k_a,
                    "field_b": orig_k_b,
                    "value_a": str(val_a),
                    "value_b": str(val_b),
                    "similarity": round(score, 3),
                    "type": f"semantic_{group_name}",
                })
                matched_a_keys.add(orig_k_a)
                matched_b_keys.add(orig_k_b)

        if not scores:
            return 0.5, {"matched_fields": [], "note": "No common or semantically aligned attribute fields found"}

        final_attr_score = float(sum(scores) / len(scores))
        return max(0.0, min(1.0, final_attr_score)), {"matched_fields": field_matches}

    @staticmethod
    def _compare_values(val_a: Any, val_b: Any) -> Tuple[float, str]:
        """Compares two attribute values (strings, numbers, etc.)."""
        # Numeric comparison
        try:
            num_a = float(val_a)
            num_b = float(val_b)
            max_num = max(abs(num_a), abs(num_b))
            if max_num == 0.0:
                return 1.0, "numeric_exact"
            diff = abs(num_a - num_b) / max_num
            return max(0.0, min(1.0, 1.0 - diff)), "numeric_relative"
        except (ValueError, TypeError):
            pass

        # String comparison
        str_a = str(val_a).strip().lower()
        str_b = str(val_b).strip().lower()

        if str_a == str_b:
            return 1.0, "string_exact"

        # Check token / word overlap for multi-word strings
        if " " in str_a or " " in str_b:
            tokens_a = set(re.findall(r"\w+", str_a))
            tokens_b = set(re.findall(r"\w+", str_b))
            if tokens_a and tokens_b:
                inter = tokens_a.intersection(tokens_b)
                union = tokens_a.union(tokens_b)
                token_sim = len(inter) / len(union)
                if token_sim > 0.0:
                    return token_sim, "token_overlap"

        return 0.0, "string_mismatch"
