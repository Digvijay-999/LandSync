from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    """Database connectivity and PostGIS status."""
    connected: bool
    postgis_installed: bool = False
    postgis_version: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """System health check payload."""
    status: str = Field(..., description="Overall service status (e.g. 'healthy', 'degraded')")
    app: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Deployment environment")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Current server timestamp (UTC)"
    )
    database: Optional[DatabaseHealth] = None
