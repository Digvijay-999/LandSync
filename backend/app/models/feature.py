import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, JSON, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator
from geoalchemy2 import Geometry
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry.base import BaseGeometry
from shapely import to_wkt, from_wkt

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.dataset import DatasetVersion


class SpatialGeometry(TypeDecorator):
    """
    PostGIS Geometry column in PostgreSQL with native GIST indexing.
    Falls back seamlessly to Text/WKT in SQLite during automated unit tests.
    """

    impl = Text
    cache_ok = True
    use_N_D_index = False

    def __init__(self, geometry_type: str = "GEOMETRY", srid: int = 4326, spatial_index: bool = True):

        super().__init__()
        self.geometry_type = geometry_type
        self.srid = srid
        self.spatial_index = spatial_index

    def load_dialect_impl(self, dialect):
        if dialect is not None and dialect.name == "postgresql":
            return dialect.type_descriptor(
                Geometry(
                    geometry_type=self.geometry_type,
                    srid=self.srid,
                    spatial_index=self.spatial_index,
                )
            )
        elif dialect is None:
            return Geometry(
                geometry_type=self.geometry_type,
                srid=self.srid,
                spatial_index=self.spatial_index,
            )
        return dialect.type_descriptor(Text())


    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            if isinstance(value, BaseGeometry):
                return from_shape(value, srid=self.srid)
            return value
        else:
            if isinstance(value, BaseGeometry):
                return to_wkt(value)
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, str):
            try:
                return from_wkt(value)
            except Exception:
                return value
        return value


class SourceFeature(Base):
    """
    Represents an immutable vector feature as originally ingested from the source file.
    Preserves exact source attributes and native geometry coordinates.
    """

    __tablename__ = "source_features"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_feature_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    geometry: Mapped[Any] = mapped_column(
        SpatialGeometry("GEOMETRY", srid=4326, spatial_index=True),
        nullable=True,
    )
    properties: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    source_crs: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="EPSG:4326",
    )
    geometry_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Unknown",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    dataset_version: Mapped["DatasetVersion"] = relationship(
        "DatasetVersion",
        back_populates="source_features",
    )
    canonical_feature: Mapped[Optional["CanonicalFeature"]] = relationship(
        "CanonicalFeature",
        back_populates="source_feature",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<SourceFeature id={self.id} fid='{self.source_feature_id}' type='{self.geometry_type}'>"


class CanonicalFeature(Base, TimestampMixin):
    """
    Represents the harmonized, normalized spatial feature projected to the project's target CRS.
    Acts as the canonical reference for spatial candidate generation and matching.
    """

    __tablename__ = "canonical_features"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_features.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    geometry: Mapped[Any] = mapped_column(
        SpatialGeometry("GEOMETRY", srid=4326, spatial_index=True),
        nullable=True,
    )
    geometry_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Unknown",
    )
    canonical_properties: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    source_crs: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    target_crs: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="EPSG:4326",
    )

    # Relationships
    dataset_version: Mapped["DatasetVersion"] = relationship(
        "DatasetVersion",
        back_populates="canonical_features",
    )
    source_feature: Mapped["SourceFeature"] = relationship(
        "SourceFeature",
        back_populates="canonical_feature",
    )

    def __repr__(self) -> str:
        return f"<CanonicalFeature id={self.id} src_fid={self.source_feature_id} type='{self.geometry_type}'>"
