import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Boolean, JSON, ForeignKey, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.dataset import Dataset
    from app.models.feature import CanonicalFeature


class MatchRun(Base, TimestampMixin):
    """
    Represents an execution run of the geospatial feature matching engine.
    Stores run-level parameters, execution metadata, and aggregate matching results.
    """

    __tablename__ = "match_runs"

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
    source_dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_dataset_ids: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    configuration: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    total_features_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_candidates: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_matches: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_possible_matches: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_conflicts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_unmatched: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    quality_metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="matching_runs",
    )
    source_dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        foreign_keys=[source_dataset_id],
    )
    matches: Mapped[List["FeatureMatch"]] = relationship(
        "FeatureMatch",
        back_populates="match_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<MatchRun id={self.id} status='{self.status}' processed={self.total_features_processed} matches={self.total_matches}>"


class FeatureMatch(Base, TimestampMixin):
    """
    Represents a pairwise candidate evaluation result between a source feature
    and a candidate feature, or an explicit UNMATCHED classification for a source feature.
    """

    __tablename__ = "feature_matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    match_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("match_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_features.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_feature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_features.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_dataset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Individual normalized signal scores (0.0 to 1.0, or None if not applicable)
    spatial_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    centroid_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    area_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    geometry_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    attribute_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Weighted final overall score (0.0 to 1.0)
    overall_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        index=True,
    )

    # Match classification status: 'matched', 'possible_match', 'conflict', 'unmatched'
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Milestone 3.1: Candidate Ranking, Roles, and Quality Semantics
    rank: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    is_best_candidate: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    candidate_role: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    score_gap: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    candidate_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Milestone 4: Human Review & Audit Layer
    # Review statuses: 'PENDING', 'ACCEPTED', 'REJECTED', 'FLAGGED'
    review_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
        index=True,
    )

    # Structured machine-readable explanation (component scores, reasons, field alignments)
    explanation: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    scoring_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="v1.0",
    )

    # Relationships
    match_run: Mapped["MatchRun"] = relationship(
        "MatchRun",
        back_populates="matches",
    )
    source_feature: Mapped["CanonicalFeature"] = relationship(
        "CanonicalFeature",
        foreign_keys=[source_feature_id],
        lazy="joined",
    )
    candidate_feature: Mapped[Optional["CanonicalFeature"]] = relationship(
        "CanonicalFeature",
        foreign_keys=[candidate_feature_id],
        lazy="joined",
    )
    source_dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        foreign_keys=[source_dataset_id],
        lazy="joined",
    )
    candidate_dataset: Mapped[Optional["Dataset"]] = relationship(
        "Dataset",
        foreign_keys=[candidate_dataset_id],
        lazy="joined",
    )
    reviews: Mapped[List["MatchReview"]] = relationship(
        "MatchReview",
        back_populates="feature_match",
        cascade="all, delete-orphan",
        order_by="MatchReview.created_at.desc()",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_feature_matches_run_status", "match_run_id", "status"),
        Index("ix_feature_matches_run_score", "match_run_id", "overall_score"),
        Index("ix_feature_matches_run_best", "match_run_id", "is_best_candidate"),
        Index("ix_feature_matches_run_role", "match_run_id", "candidate_role"),
        Index("ix_feature_matches_run_review_status", "match_run_id", "review_status"),
        Index("ix_feature_matches_source_rank", "source_feature_id", "rank"),
    )

    def __repr__(self) -> str:
        return f"<FeatureMatch id={self.id} status='{self.status}' review='{self.review_status}' score={self.overall_score:.2f}>"


class MatchReview(Base, TimestampMixin):
    """
    Audit trail of human review decisions made on a FeatureMatch.
    Preserves full decision history with decision, optional reviewer comment,
    and timestamps without mutating machine matching results.
    """

    __tablename__ = "match_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    feature_match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feature_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )  # "ACCEPTED", "REJECTED", "FLAGGED"
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    feature_match: Mapped["FeatureMatch"] = relationship(
        "FeatureMatch",
        back_populates="reviews",
    )

    __table_args__ = (
        Index("ix_match_reviews_match_created", "feature_match_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<MatchReview id={self.id} match_id={self.feature_match_id} decision='{self.decision}'>"

