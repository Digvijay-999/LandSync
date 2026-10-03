import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import (
    String,
    ForeignKey,
    JSON,
    DateTime,
    Index,
    Float,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.unified import UnifiedLandRecord
    from app.models.matching import FeatureMatch
    from app.models.validation import ValidationResult
    from app.models.adjudication import HumanReviewDecision


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


class ProvenanceRecord(Base):
    """
    Stage 13 Persistent Provenance & Lineage Record.
    Anchors the authoritative lineage for a UnifiedLandRecord, connecting
    contributing datasets, source features, match runs, harmonization,
    conflicts, validation results, confidence scores, and human review decisions.
    """

    __tablename__ = "provenance_records"

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
    harmonized_record_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    record_identifier: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    # Lineage references (UUIDs and IDs)
    source_dataset_ids: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    source_feature_ids: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    source_record_identifiers: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    feature_match_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feature_matches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    matched_record_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    conflict_ids: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    validation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    human_review_decision_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("human_review_decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Lineage state & metrics
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    confidence_bucket: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    resolution_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UNIFIED",
        index=True,
    )  # UNIFIED, REJECTED
    lineage_completeness_pct: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=100.0,
    )
    lineage_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="COMPLETE",
        index=True,
    )  # COMPLETE, PARTIAL, QUARANTINED
    missing_stages: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Structured Lineage Graph & Detailed Audit Payloads
    lineage_graph: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    metadata_trail: Mapped[Dict[str, Any]] = mapped_column(
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    unified_record: Mapped["UnifiedLandRecord"] = relationship("UnifiedLandRecord")
    feature_match: Mapped[Optional["FeatureMatch"]] = relationship("FeatureMatch")
    validation_result: Mapped[Optional["ValidationResult"]] = relationship("ValidationResult")
    human_review_decision: Mapped[Optional["HumanReviewDecision"]] = relationship("HumanReviewDecision")

    __table_args__ = (
        UniqueConstraint("project_id", "unified_land_record_id", name="uq_project_unified_record_provenance"),
        Index("ix_provenance_records_project_created", "project_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ProvenanceRecord id={self.id} record='{self.record_identifier}' completeness={self.lineage_completeness_pct}%>"
