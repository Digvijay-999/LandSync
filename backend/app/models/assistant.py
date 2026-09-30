import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import (
    String,
    ForeignKey,
    JSON,
    DateTime,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class VectorColumn(TypeDecorator):
    """
    Vector column supporting float embedding vectors.
    Stores dense vector embeddings as JSON arrays for seamless cross-dialect
    compatibility across PostgreSQL and SQLite unit tests.
    """
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 384):
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(JSON())


class AssistantDocument(Base):
    """
    Structured textual evidence document and vector embedding representation
    of LandSync entities (Projects, Datasets, Unified Records, Conflicts, Provenance).
    """

    __tablename__ = "assistant_documents"

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
    document_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # PROJECT, DATASET, UNIFIED_RECORD, SOURCE_FEATURE, CONFLICT, PROVENANCE, REVIEW, AUDIT
    entity_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )  # e.g. "ULR-000001", "CAD-101", "land_use", etc.
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    doc_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    embedding: Mapped[Optional[List[float]]] = mapped_column(
        VectorColumn(dim=384),
        nullable=True,
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

    __table_args__ = (
        Index("ix_assistant_docs_project_category", "project_id", "document_category"),
        Index("ix_assistant_docs_project_entity", "project_id", "entity_id"),
    )

    def __repr__(self) -> str:
        return f"<AssistantDocument {self.document_category} entity={self.entity_id} title='{self.title}'>"
