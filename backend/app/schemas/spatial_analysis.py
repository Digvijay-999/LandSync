import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator


class SpatialAnalysisType(str, Enum):
    PROXIMITY = "PROXIMITY"
    BUFFER = "BUFFER"
    INTERSECTION = "INTERSECTION"
    CONTAINMENT = "CONTAINMENT"
    OVERLAP = "OVERLAP"
    NEAREST = "NEAREST"
    STATISTICS = "STATISTICS"
    DATASET_COMPARISON = "DATASET_COMPARISON"
    CONFLICT_CLUSTERS = "CONFLICT_CLUSTERS"
    VERSION_COMPARISON = "VERSION_COMPARISON"


class ProximityAnalysisRequest(BaseModel):
    project_id: uuid.UUID = Field(..., description="Project workspace ID")
    target_dataset_id: Optional[uuid.UUID] = Field(None, description="Dataset to search within")
    reference_dataset_id: Optional[uuid.UUID] = Field(None, description="Dataset providing reference features")
    reference_feature_id: Optional[str] = Field(None, description="Feature ID or identifier to measure distance from")
    target_geometry: Optional[Dict[str, Any]] = Field(None, description="Target GeoJSON geometry to measure distance from")
    latitude: Optional[float] = Field(None, description="Latitude for point-based proximity")
    longitude: Optional[float] = Field(None, description="Longitude for point-based proximity")
    distance: Optional[float] = Field(None, description="Search radius (alias for distance_meters)")
    distance_meters: float = Field(100.0, ge=0.0, le=50000.0, description="Search radius in meters")
    unit: Optional[str] = Field("meters", description="Distance units: meters, kilometers, feet")
    limit: int = Field(50, ge=1, le=500, description="Maximum features to return")

    @model_validator(mode="before")
    @classmethod
    def normalize_inputs(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "distance" in data and data["distance"] is not None:
                dist = float(data["distance"])
                if dist < 0:
                    raise ValueError("Distance cannot be negative")
                unit = str(data.get("unit") or "meters").lower()
                if unit in ("km", "kilometers"):
                    dist *= 1000.0
                elif unit in ("ft", "feet"):
                    dist *= 0.3048
                data["distance_meters"] = dist
            if "target_geometry" in data and data["target_geometry"]:
                geom = data["target_geometry"]
                if isinstance(geom, dict):
                    coords = geom.get("coordinates")
                    if geom.get("type") == "Point" and coords and len(coords) >= 2:
                        data.setdefault("longitude", coords[0])
                        data.setdefault("latitude", coords[1])
        return data


class BufferAnalysisRequest(BaseModel):
    project_id: uuid.UUID = Field(..., description="Project workspace ID")
    feature_id: Optional[str] = Field(None, description="Feature ID to buffer")
    dataset_id: Optional[uuid.UUID] = Field(None, description="Dataset containing feature")
    target_geometry: Optional[Dict[str, Any]] = Field(None, description="Target GeoJSON geometry to buffer")
    latitude: Optional[float] = Field(None, description="Latitude for point buffer")
    longitude: Optional[float] = Field(None, description="Longitude for point buffer")
    distance: Optional[float] = Field(None, description="Buffer distance (alias for distance_meters)")
    distance_meters: float = Field(50.0, ge=0.0, le=10000.0, description="Buffer distance in meters")
    unit: Optional[str] = Field("meters", description="Distance units")
    target_dataset_id: Optional[uuid.UUID] = Field(None, description="Optional dataset to intersect with buffer")

    @model_validator(mode="before")
    @classmethod
    def normalize_inputs(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "distance" in data and data["distance"] is not None:
                dist = float(data["distance"])
                unit = str(data.get("unit") or "meters").lower()
                if unit in ("km", "kilometers"):
                    dist *= 1000.0
                elif unit in ("ft", "feet"):
                    dist *= 0.3048
                data["distance_meters"] = dist
            if "target_geometry" in data and data["target_geometry"]:
                geom = data["target_geometry"]
                if isinstance(geom, dict):
                    coords = geom.get("coordinates")
                    if geom.get("type") == "Point" and coords and len(coords) >= 2:
                        data.setdefault("longitude", coords[0])
                        data.setdefault("latitude", coords[1])
        return data


class IntersectionAnalysisRequest(BaseModel):
    project_id: uuid.UUID = Field(..., description="Project workspace ID")
    dataset_a_id: uuid.UUID = Field(..., description="First dataset ID")
    dataset_b_id: uuid.UUID = Field(..., description="Second dataset ID")
    min_overlap_pct: float = Field(0.0, ge=0.0, le=100.0, description="Minimum overlap percentage to report")
    limit: int = Field(100, ge=1, le=1000, description="Maximum intersection pairs")


class ContainmentAnalysisRequest(BaseModel):
    project_id: uuid.UUID = Field(..., description="Project workspace ID")
    container_dataset_id: Optional[uuid.UUID] = Field(None, description="Dataset containing bounding/zoning features")
    contained_dataset_id: Optional[uuid.UUID] = Field(None, description="Dataset containing features to test for containment")
    container_feature_id: Optional[str] = Field(None, description="Specific container feature to test against")
    container_geometry: Optional[Dict[str, Any]] = Field(None, description="Container polygon geometry")
    containment_mode: Optional[str] = Field("contains", description="'contains' or 'contained_by'")
    limit: int = Field(100, ge=1, le=1000)


class OverlapAnalysisRequest(BaseModel):
    project_id: uuid.UUID = Field(..., description="Project workspace ID")
    dataset_a_id: uuid.UUID = Field(..., description="First dataset ID")
    dataset_b_id: uuid.UUID = Field(..., description="Second dataset ID")
    feature_a_id: Optional[str] = Field(None, description="Specific feature in dataset A")
    feature_b_id: Optional[str] = Field(None, description="Specific feature in dataset B")
    limit: int = Field(100, ge=1, le=1000)


class NearestFeaturesRequest(BaseModel):
    project_id: uuid.UUID = Field(..., description="Project workspace ID")
    reference_feature_id: Optional[str] = Field(None, description="Reference feature")
    target_geometry: Optional[Dict[str, Any]] = Field(None, description="Target GeoJSON geometry for nearest search")
    latitude: Optional[float] = Field(None, description="Reference latitude")
    longitude: Optional[float] = Field(None, description="Reference longitude")
    candidate_dataset_id: Optional[uuid.UUID] = Field(None, description="Dataset to search within")
    limit: int = Field(5, ge=1, le=50, description="Number of nearest neighbors")

    @model_validator(mode="before")
    @classmethod
    def normalize_inputs(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "target_geometry" in data and data["target_geometry"]:
                geom = data["target_geometry"]
                if isinstance(geom, dict):
                    coords = geom.get("coordinates")
                    if geom.get("type") == "Point" and coords and len(coords) >= 2:
                        data.setdefault("longitude", coords[0])
                        data.setdefault("latitude", coords[1])
        return data


class SpatialStatisticsRequest(BaseModel):
    project_id: uuid.UUID = Field(..., description="Project workspace ID")
    dataset_id: Optional[uuid.UUID] = Field(None, description="Optional specific dataset; defaults to all project features")


class DatasetComparisonRequest(BaseModel):
    project_id: uuid.UUID = Field(..., description="Project workspace ID")
    dataset_a_id: uuid.UUID = Field(..., description="Dataset A (e.g. Cadastral)")
    dataset_b_id: uuid.UUID = Field(..., description="Dataset B (e.g. Drone Ortho)")


class SpatialConflictAnalysisRequest(BaseModel):
    project_id: uuid.UUID = Field(..., description="Project workspace ID")
    limit: int = Field(50, ge=1, le=200)


# Response Models

class SpatialFeatureItem(BaseModel):
    id: str
    identifier: str
    dataset_id: Optional[str] = None
    dataset_name: Optional[str] = None
    geometry_type: str = "Polygon"
    geometry: Optional[Dict[str, Any]] = None  # GeoJSON Geometry object
    properties: Dict[str, Any] = Field(default_factory=dict)
    distance_meters: Optional[float] = None
    area_sqm: Optional[float] = None
    overlap_pct: Optional[float] = None


class SpatialAnalysisResult(BaseModel):
    analysis_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    project_id: uuid.UUID
    analysis_type: SpatialAnalysisType
    title: str
    description: str
    source_datasets: List[str] = Field(default_factory=list)
    input_parameters: Dict[str, Any] = Field(default_factory=dict)
    result_count: int = 0
    statistics: Dict[str, Any] = Field(default_factory=dict)
    result_geometry: Optional[Dict[str, Any]] = Field(None, description="Analytical geometry (e.g. buffer polygon)")
    result_features: List[Dict[str, Any]] = Field(default_factory=list, description="Structured feature matches")
    result_geojson: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "FeatureCollection", "features": []},
        description="GeoJSON FeatureCollection formatted for direct MapLibre rendering",
    )
    execution_time_ms: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class DatasetComparisonResult(BaseModel):
    project_id: uuid.UUID
    dataset_a_id: uuid.UUID
    dataset_a_name: str
    dataset_b_id: uuid.UUID
    dataset_b_name: str
    dataset_a_count: int
    dataset_b_count: int
    intersecting_count: int
    unmatched_a_count: int
    unmatched_b_count: int
    overlap_area_sqm: float
    overlap_percentage: float
    spatial_extent_comparison: Dict[str, Any]
    analysis: SpatialAnalysisResult


class SpatialConflictCluster(BaseModel):
    cluster_id: str
    conflict_count: int
    affected_record_ids: List[str]
    centroid: List[float]  # [lat, lon]
    bounding_box: List[float]  # [min_lon, min_lat, max_lon, max_lat]
    dominant_fields: List[str]
    dataset_pairs: List[str]


class SpatialConflictAnalysisResult(BaseModel):
    project_id: uuid.UUID
    total_conflicts: int
    cluster_count: int
    clusters: List[SpatialConflictCluster]
    dataset_pair_disagreements: Dict[str, int]
    high_conflict_areas: List[Dict[str, Any]]
    analysis: SpatialAnalysisResult


class VersionComparisonRequest(BaseModel):
    project_id: uuid.UUID = Field(..., description="Project workspace ID")
    dataset_id: uuid.UUID = Field(..., description="Dataset ID to compare versions of")
    version_a_number: int = Field(1, ge=1, description="Baseline version number")
    version_b_number: Optional[int] = Field(None, ge=1, description="Target version number (defaults to latest)")


class VersionDifferenceItem(BaseModel):
    feature_id: str
    identifier: str
    change_type: str = Field(..., description="ADDED, REMOVED, CHANGED, or UNCHANGED")
    geometry_change: bool = False
    attribute_change: bool = False
    area_delta_sqm: Optional[float] = None
    centroid_shift_meters: Optional[float] = None
    attribute_diffs: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, Any] = Field(default_factory=dict)


class VersionComparisonResult(BaseModel):
    project_id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_name: str
    version_a_number: int
    version_b_number: int
    status: str = Field("success", description="'success' or 'insufficient_versions'")
    message: Optional[str] = None
    added_count: int = 0
    removed_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    changes: List[VersionDifferenceItem] = Field(default_factory=list)
    analysis: Optional[SpatialAnalysisResult] = None


class AnalysisHistorySummary(BaseModel):
    analysis_id: uuid.UUID
    project_id: uuid.UUID
    analysis_type: SpatialAnalysisType
    title: str
    description: str
    result_count: int
    execution_time_ms: float
    created_at: datetime
    status: str = "COMPLETED"
