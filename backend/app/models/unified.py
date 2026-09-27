import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import (
    String,
    Float,
    ForeignKey,
    JSON,
    DateTime,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.feature import SpatialGeometry

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.feature import CanonicalFeature
    from app.models.matching import FeatureMatch


class UnifiedLandRecord(Base, TimestampMixin):
    """
    Represents a unified, canonical land record harmonized from multiple accepted
    source features across heterogeneous geospatial datasets.
    """

    __tablename__ = "unified_land_records"

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
    record_identifier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="ACTIVE",
        index=True,
    )  # ACTIVE, INCOMPLETE, CONFLICT
    canonical_geometry: Mapped[Any] = mapped_column(
        SpatialGeometry("GEOMETRY", srid=4326, spatial_index=True),
        nullable=True,
    )
    geometry_source_feature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_features.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    geometry_source_role: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # CADASTRAL, DRONE, MUNICIPAL, OTHER
    area: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    canonical_attributes: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="unified_records",
    )
    sources: Mapped[List["UnifiedLandRecordSource"]] = relationship(
        "UnifiedLandRecordSource",
        back_populates="unified_record",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="UnifiedLandRecordSource.created_at.asc()",
    )
    geometry_source_feature: Mapped[Optional["CanonicalFeature"]] = relationship(
        "CanonicalFeature",
        foreign_keys=[geometry_source_feature_id],
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "record_identifier",
            name="uq_project_unified_record_identifier",
        ),
        Index("ix_unified_records_project_status", "project_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<UnifiedLandRecord id={self.id} identifier='{self.record_identifier}' "
            f"status='{self.status}' sources={len(self.sources) if self.sources else 0}>"
        )


class UnifiedLandRecordSource(Base):
    """
    References a contributing source feature and its accepted match relationship
    associated with a UnifiedLandRecord.
    """

    __tablename__ = "unified_land_record_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    unified_land_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("unified_land_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_features.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_match_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feature_matches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="OTHER",
    )  # CADASTRAL, DRONE, MUNICIPAL, OTHER
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    unified_record: Mapped["UnifiedLandRecord"] = relationship(
        "UnifiedLandRecord",
        back_populates="sources",
    )
    feature: Mapped["CanonicalFeature"] = relationship(
        "CanonicalFeature",
        foreign_keys=[feature_id],
        lazy="joined",
    )
    feature_match: Mapped[Optional["FeatureMatch"]] = relationship(
        "FeatureMatch",
        foreign_keys=[feature_match_id],
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint(
            "unified_land_record_id",
            "feature_id",
            name="uq_unified_record_source_feature",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<UnifiedLandRecordSource id={self.id} record_id={self.unified_land_record_id} "
            f"feature_id={self.feature_id} role='{self.source_role}'>"
        )
