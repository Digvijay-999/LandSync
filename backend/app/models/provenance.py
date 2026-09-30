import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import (
    String,
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
    from app.models.unified import UnifiedLandRecord


class ProvenanceEvent(Base):
    """
    Audit and lifecycle event recording provenance-relevant actions such as
    exports created, records synthesized, and human review reconciliations.
    """

    __tablename__ = "provenance_events"

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
    unified_land_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("unified_land_records.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # EXPORT_CREATED, RECORD_CREATED, RECORD_REBUILT, etc.
    source_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # PROJECT_EXPORT, RECORD_EXPORT, UNIFIED_RECORD
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    event_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    unified_record: Mapped[Optional["UnifiedLandRecord"]] = relationship("UnifiedLandRecord")

    __table_args__ = (
        Index("ix_provenance_events_project_created", "project_id", "created_at"),
        Index("ix_provenance_events_record_created", "unified_land_record_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ProvenanceEvent id={self.id} type='{self.event_type}' project_id={self.project_id}>"
