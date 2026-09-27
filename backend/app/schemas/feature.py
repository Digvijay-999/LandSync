import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.dataset import BoundingBox


class GeoJSONFeature(BaseModel):
    """Standard GeoJSON Feature representation for MapLibre rendering."""
    type: str = "Feature"
    id: str
    geometry: Optional[Dict[str, Any]] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class GeoJSONFeatureCollection(BaseModel):
    """Standard GeoJSON FeatureCollection response."""
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]
    crs: Optional[Dict[str, Any]] = None
    total: int


class FeatureRead(BaseModel):
    """Detailed feature read schema."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_version_id: uuid.UUID
    source_feature_id: Optional[str] = None
    geometry_type: str
    properties: Dict[str, Any]
    source_crs: str
    target_crs: Optional[str] = None
    created_at: datetime


class FeatureListResponse(BaseModel):
    items: List[FeatureRead]
    total: int


class ProjectLayer(BaseModel):
    """Representation of an ingested dataset layer on the interactive map."""
    id: str
    dataset_id: str
    name: str
    source_format: str
    geometry_type: str
    feature_count: int
    source_crs: str
    target_crs: str
    bounds: Optional[BoundingBox] = None
    geojson_url: str
    color: Optional[str] = None


class ProjectLayersResponse(BaseModel):
    """All active spatial layers in a project workspace."""
    project_id: uuid.UUID
    project_name: str
    target_crs: str
    combined_bounds: Optional[BoundingBox] = None
    layers: List[ProjectLayer]
