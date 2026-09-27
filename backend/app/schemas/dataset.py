import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class BoundingBox(BaseModel):
    """Spatial bounding box extent."""
    min_x: float = Field(..., description="Minimum X coordinate / longitude")
    min_y: float = Field(..., description="Minimum Y coordinate / latitude")
    max_x: float = Field(..., description="Maximum X coordinate / longitude")
    max_y: float = Field(..., description="Maximum Y coordinate / latitude")


class DatasetField(BaseModel):
    """Profile of a single attribute field / column."""
    name: str
    data_type: str
    null_count: int
    unique_count: int


class GeneralProfile(BaseModel):
    filename: str
    format: str
    file_size: int
    feature_count: int


class GeometryProfile(BaseModel):
    geometry_type: str
    geometry_type_distribution: Dict[str, int]
    geometry_count: int
    valid_geometry_count: int
    invalid_geometry_count: int
    empty_geometry_count: int
    validity_percentage: float


class SpatialProfile(BaseModel):
    crs: Optional[str] = None
    crs_name: Optional[str] = None
    is_geographic: Optional[bool] = None
    bounds: Optional[BoundingBox] = None


class AttributeProfile(BaseModel):
    field_count: int
    fields: List[DatasetField]


class DatasetProfile(BaseModel):
    """Complete dataset profiling result generated during ingestion."""
    general: GeneralProfile
    geometry: GeometryProfile
    spatial: SpatialProfile
    attributes: AttributeProfile


class DatasetVersionRead(BaseModel):
    """Read schema for a dataset version."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    version_number: int
    file_size: int
    checksum: Optional[str] = None
    created_at: datetime


class DatasetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source_filename: str
    source_format: str
    source_type: str = "vector"
    status: str = "ready"
    feature_count: int = 0
    geometry_type: str = "Unknown"
    detected_crs: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None
    file_size: int = 0


class DatasetRead(DatasetBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DatasetDetailResponse(DatasetRead):
    """Detailed response including full profiling data and version history."""
    profile: Optional[DatasetProfile] = None
    versions: List[DatasetVersionRead] = []


class DatasetListResponse(BaseModel):
    items: List[DatasetRead]
    total: int
