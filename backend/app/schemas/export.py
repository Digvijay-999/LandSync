import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class ExportCreateRequest(BaseModel):
    """Request payload for generating an export deliverable."""
    format: str = Field(
        default="geojson",
        description="Deliverable format: 'geojson', 'gpkg', or 'csv'",
    )
    include_quarantined: bool = Field(
        default=False,
        description="Whether to include rejected/quarantined records alongside authoritative records",
    )


class ExportJobItem(BaseModel):
    """Summary of a persistent export deliverable job."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    format: str
    status: str
    filename: str
    file_size_bytes: int
    record_count: int
    authoritative_count: int
    quarantined_count: int
    include_quarantined: bool
    crs: str
    sha256_checksum: Optional[str] = None
    manifest_data: Dict[str, Any] = Field(default_factory=dict)
    download_url: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ExportJobListResponse(BaseModel):
    """List response for export history."""
    items: List[ExportJobItem]
    total: int


class ExportManifestResponse(BaseModel):
    """Defensible export deliverable manifest."""
    project_id: str
    project_name: str
    export_id: str
    export_timestamp: str
    export_format: str
    pipeline_version: str
    crs: str
    total_records: int
    authoritative_records: int
    quarantined_records: int
    include_quarantined: bool
    stage12_execution_id: Optional[str] = None
    stage13_execution_id: Optional[str] = None
    data_generation_timestamp: str
    schema_version: str
    file_name: str
    file_size_bytes: int
    sha256_checksum: Optional[str] = None


class Stage14ExecutionResponse(BaseModel):
    """Response returned upon executing Pipeline Stage 14: Export."""
    execution_id: uuid.UUID
    stage_id: str = "export"
    stage_number: int = 14
    status: str = "completed"
    message: str
    authoritative_records_count: int
    quarantined_records_count: int
    total_records_count: int
    export_job: ExportJobItem
    executed_at: datetime


class Stage14StatusResponse(BaseModel):
    """Live status and telemetry for Stage 14 Export."""
    status: str  # ready, completed, disabled, running
    prerequisites_met: bool
    prerequisites_message: Optional[str] = None
    authoritative_records_count: int
    quarantined_records_count: int
    total_records_count: int
    valid_geometry_count: int
    provenance_coverage_pct: float
    project_crs: str
    available_formats: List[str]
    recent_exports: List[ExportJobItem] = Field(default_factory=list)
    last_run_at: Optional[datetime] = None
