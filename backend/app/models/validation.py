import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.feature import CanonicalFeature


class ValidationResult(Base):
    """
    Stage 09 Validation Result Record.
    Captures multi-dimensional validation for a harmonized parcel candidate pair:
    - Geometry validity (ST_IsValid, emptiness, nullity)
    - Topological integrity (self-intersection, overlap ratio, centroid distance, containment)
    - Area tolerance compliance
    - Semantic attribute business rules
    - Conflict-aware resolution state
    - Overall PASS / WARNING / FAIL classification
    """

    __tablename__ = "validation_results"

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
    harmonized_record_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    source_feature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_features.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    candidate_feature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_features.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_identifier: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    candidate_identifier: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Sub-rule validation statuses
    overall_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PASS",
        index=True,
    )
    geometry_validity_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PASS",
    )
    topology_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PASS",
    )
    area_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PASS",
    )
    semantic_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PASS",
    )
    conflict_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PASS",
    )

    # Reasons & Metric payloads
    failure_reasons: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    warning_reasons: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    geometry_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    topology_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    area_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    semantic_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    conflict_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # Idempotency & Timestamps
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    source_feature: Mapped[Optional["CanonicalFeature"]] = relationship(
        "CanonicalFeature", foreign_keys=[source_feature_id], lazy="joined"
    )
    candidate_feature: Mapped[Optional["CanonicalFeature"]] = relationship(
        "CanonicalFeature", foreign_keys=[candidate_feature_id], lazy="joined"
    )

    __table_args__ = (
        Index("ix_validation_results_proj_status", "project_id", "overall_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<ValidationResult id={self.id} record={self.harmonized_record_id} "
            f"overall={self.overall_status}>"
        )
