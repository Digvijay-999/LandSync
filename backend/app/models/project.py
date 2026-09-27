import uuid
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.dataset import Dataset
    from app.models.matching import MatchRun
    from app.models.unified import UnifiedLandRecord



class Project(Base, TimestampMixin):
    """
    Project model representing a geospatial harmonization workspace.
    Projects organize datasets, harmonization pipelines, and unified records.
    """

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    target_crs: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="EPSG:4326",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
    )

    # Relationships
    datasets: Mapped[List["Dataset"]] = relationship(
        "Dataset",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    matching_runs: Mapped[List["MatchRun"]] = relationship(
        "MatchRun",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    unified_records: Mapped[List["UnifiedLandRecord"]] = relationship(
        "UnifiedLandRecord",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:

        return f"<Project id={self.id} name='{self.name}' status='{self.status}'>"
