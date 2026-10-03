import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import (
    String,
    ForeignKey,
    JSON,
    DateTime,
    Text,
    Float,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.unified import UnifiedLandRecord
    from app.models.feature import CanonicalFeature


class AttributeConflict(Base):
    """
    Represents an attribute disagreement or discrepancy between multiple
    source features contributing to a UnifiedLandRecord.
    """

    __tablename__ = "attribute_conflicts"

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
    unified_land_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("unified_land_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attribute_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )  # e.g. "land_use", "area", "address", "zoning"
    conflict_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # VALUE_MISMATCH, NUMERIC_DIFFERENCE, NULL_VALUE_CONFLICT
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MEDIUM",
        index=True,
    )  # HIGH, MEDIUM, LOW
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="UNRESOLVED",
        index=True,
    )  # UNRESOLVED, RESOLVED, DISMISSED
    detected_values: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    resolution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conflict_resolutions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    unified_record: Mapped["UnifiedLandRecord"] = relationship(
        "UnifiedLandRecord",
        foreign_keys=[unified_land_record_id],
    )
    resolution: Mapped[Optional["ConflictResolution"]] = relationship(
        "ConflictResolution",
        foreign_keys=[resolution_id],
        post_update=True,
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "unified_land_record_id",
            "attribute_name",
            name="uq_record_attribute_conflict",
        ),
        Index("ix_attribute_conflicts_project_status", "project_id", "status"),
        Index("ix_attribute_conflicts_record_status", "unified_land_record_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<AttributeConflict id={self.id} record_id={self.unified_land_record_id} "
            f"attr='{self.attribute_name}' type='{self.conflict_type}' status='{self.status}'>"
        )


class ConflictResolution(Base):
    """
    Immutable audit record of a human reviewer decision resolving or dismissing
    an AttributeConflict on a UnifiedLandRecord.
    """

    __tablename__ = "conflict_resolutions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    conflict_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attribute_conflicts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resolution_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # SOURCE_SELECTION, MANUAL_VALUE, DISMISSED
    selected_source_feature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_features.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    selected_source_role: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # CADASTRAL, DRONE, MUNICIPAL, etc.
    resolved_value: Mapped[Any] = mapped_column(
        JSON,
        nullable=False,
    )
    comment: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    resolved_by: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    conflict: Mapped["AttributeConflict"] = relationship(
        "AttributeConflict",
        foreign_keys=[conflict_id],
    )
    selected_feature: Mapped[Optional["CanonicalFeature"]] = relationship(
        "CanonicalFeature",
        foreign_keys=[selected_source_feature_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<ConflictResolution id={self.id} conflict_id={self.conflict_id} "
            f"type='{self.resolution_type}' val={self.resolved_value}>"
        )


class GeospatialConflict(Base):
    """
    Stage 08 Geospatial Conflict Record.
    Captures attribute disagreements, geometry variances, area discrepancies,
    mutation divergences, and risk discrepancies identified across harmonized candidate feature pairs.
    """

    __tablename__ = "geospatial_conflicts"

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
    conflict_type: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="ATTRIBUTE",
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="MEDIUM",
        index=True,
    )
    severity_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="OPEN",
        index=True,
    )
    source_a: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    source_b: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    value_a: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_b: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_value_a: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_value_b: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discrepancy_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discrepancy_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    detection_rule: Mapped[str] = mapped_column(String(100), nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    geometry_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
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
        index=True,
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
        Index("ix_geospatial_conflicts_proj_status", "project_id", "status"),
        Index("ix_geospatial_conflicts_proj_severity", "project_id", "severity"),
    )

    def __repr__(self) -> str:
        return (
            f"<GeospatialConflict id={self.id} project_id={self.project_id} "
            f"type='{self.conflict_type}' field='{self.field_name}' severity='{self.severity}' status='{self.status}'>"
        )
