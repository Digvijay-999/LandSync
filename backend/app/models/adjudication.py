import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import String, Text, Boolean, JSON, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class HumanReviewDecision(Base, TimestampMixin):
    """
    Stage 11 Human Review Adjudication Record.
    Stores explicit reviewer decisions:
    - ACCEPT_SOURCE_A
    - ACCEPT_SOURCE_B
    - MERGE_RECONCILE (authoritative field selections)
    - REJECT_UNRESOLVED
    Along with reviewer notes, previous state, resulting state, and conflict override flags.
    """

    __tablename__ = "human_review_decisions"

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
    feature_match_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feature_matches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Adjudication Decision
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # ACCEPT_SOURCE_A, ACCEPT_SOURCE_B, MERGE_RECONCILE, REJECT_UNRESOLVED

    adjudication_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="RESOLVED",
        index=True,
    )  # RESOLVED, REJECTED, UNRESOLVED

    reviewer_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Lead GIS Adjudicator",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Reconciled / Authoritative Values
    authoritative_geometry_source: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # SOURCE_A, SOURCE_B, CUSTOM

    authoritative_attributes: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # State tracking and overrides
    previous_state: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    resulting_state: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    override_applied: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    source_feature: Mapped[Optional["CanonicalFeature"]] = relationship(
        "CanonicalFeature",
        foreign_keys=[source_feature_id],
        lazy="joined",
    )
    candidate_feature: Mapped[Optional["CanonicalFeature"]] = relationship(
        "CanonicalFeature",
        foreign_keys=[candidate_feature_id],
        lazy="joined",
    )
    feature_match: Mapped[Optional["FeatureMatch"]] = relationship(
        "FeatureMatch",
        foreign_keys=[feature_match_id],
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_human_review_project_status", "project_id", "adjudication_status"),
        Index("ix_human_review_project_action", "project_id", "action"),
    )

    def __repr__(self) -> str:
        return (
            f"<HumanReviewDecision id={self.id} project_id={self.project_id} "
            f"record='{self.harmonized_record_id}' action='{self.action}' status='{self.adjudication_status}'>"
        )
