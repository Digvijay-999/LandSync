import uuid
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, Integer, BigInteger, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.feature import SourceFeature, CanonicalFeature



class Dataset(Base, TimestampMixin):
    """
    Dataset model representing an ingested geospatial dataset (vector file).
    Belongs to a Project and can have multiple versions.
    """

    __tablename__ = "datasets"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_format: Mapped[str] = mapped_column(String(50), nullable=False)  # geojson, shapefile, geopackage, csv
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="vector")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ready")

    feature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    geometry_type: Mapped[str] = mapped_column(String(100), nullable=False, default="Unknown")
    detected_crs: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bounding_box: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    profile_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="datasets")
    versions: Mapped[List["DatasetVersion"]] = relationship(
        "DatasetVersion",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetVersion.version_number.desc()",
        lazy="selectin",
    )


    def __repr__(self) -> str:
        return f"<Dataset id={self.id} name='{self.name}' format='{self.source_format}' count={self.feature_count}>"


class DatasetVersion(Base, TimestampMixin):
    """
    DatasetVersion model representing a versioned physical payload and profile snapshot.
    """

    __tablename__ = "dataset_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    profile_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="versions")
    source_features: Mapped[List["SourceFeature"]] = relationship(
        "SourceFeature",
        back_populates="dataset_version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    canonical_features: Mapped[List["CanonicalFeature"]] = relationship(
        "CanonicalFeature",
        back_populates="dataset_version",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:

        return f"<DatasetVersion id={self.id} dataset_id={self.dataset_id} v={self.version_number}>"
