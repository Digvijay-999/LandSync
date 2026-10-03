import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    Boolean,
    ForeignKey,
    JSON,
    DateTime,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class ExportJob(Base):
    """
    Stage 14 Persistent Export Job.
    Tracks export operations, deliverable artifact metadata, record counts,
    and manifest linkages for defensible project outputs.
    """

    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # geojson, csv, gpkg
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="COMPLETED",
        index=True,
    )  # PENDING, PROCESSING, COMPLETED, FAILED
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )
    record_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    authoritative_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    quarantined_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    include_quarantined: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    crs: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="EPSG:4326",
    )
    sha256_checksum: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    manifest_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")

    __table_args__ = (
        Index("ix_export_jobs_project_created", "project_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ExportJob id={self.id} format='{self.format}' records={self.record_count} status='{self.status}'>"
