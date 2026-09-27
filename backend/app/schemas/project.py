import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    """Base project schema with shared fields."""
    name: str = Field(..., min_length=1, max_length=255, description="Project workspace name")
    description: Optional[str] = Field(None, description="Optional project description")
    target_crs: str = Field(
        default="EPSG:4326",
        description="Target coordinate reference system for normalized data"
    )
    status: str = Field(
        default="active",
        description="Project lifecycle status"
    )


class ProjectCreate(ProjectBase):
    """Payload for creating a new project."""
    pass


class ProjectUpdate(BaseModel):
    """Payload for updating an existing project."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    target_crs: Optional[str] = None
    status: Optional[str] = None


class ProjectRead(ProjectBase):
    """Project schema returned to API clients."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """List response envelope for projects."""
    items: List[ProjectRead]
    total: int
