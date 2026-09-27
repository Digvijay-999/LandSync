"""Add match_runs and feature_matches tables for spatial feature matching

Revision ID: 0004_matching
Revises: 0003_features
Create Date: 2026-09-27 04:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_matching"
down_revision: Union[str, None] = "0003_features"

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create match_runs table
    op.create_table(
        "match_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("candidate_dataset_ids", sa.JSON(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("total_features_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_matches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_possible_matches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_conflicts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_unmatched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_match_runs_id", "match_runs", ["id"])
    op.create_index("ix_match_runs_project_id", "match_runs", ["project_id"])
    op.create_index("ix_match_runs_source_dataset_id", "match_runs", ["source_dataset_id"])
    op.create_index("ix_match_runs_status", "match_runs", ["status"])

    # 2. Create feature_matches table
    op.create_table(
        "feature_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "match_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("match_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_features.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_features.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "source_dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("spatial_score", sa.Float(), nullable=True),
        sa.Column("centroid_score", sa.Float(), nullable=True),
        sa.Column("area_score", sa.Float(), nullable=True),
        sa.Column("geometry_score", sa.Float(), nullable=True),
        sa.Column("attribute_score", sa.Float(), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column("scoring_version", sa.String(length=50), nullable=False, server_default="v1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feature_matches_id", "feature_matches", ["id"])
    op.create_index("ix_feature_matches_match_run_id", "feature_matches", ["match_run_id"])
    op.create_index("ix_feature_matches_project_id", "feature_matches", ["project_id"])
    op.create_index("ix_feature_matches_source_feature_id", "feature_matches", ["source_feature_id"])
    op.create_index("ix_feature_matches_candidate_feature_id", "feature_matches", ["candidate_feature_id"])
    op.create_index("ix_feature_matches_source_dataset_id", "feature_matches", ["source_dataset_id"])
    op.create_index("ix_feature_matches_candidate_dataset_id", "feature_matches", ["candidate_dataset_id"])
    op.create_index("ix_feature_matches_status", "feature_matches", ["status"])
    op.create_index("ix_feature_matches_overall_score", "feature_matches", ["overall_score"])
    op.create_index("ix_feature_matches_run_status", "feature_matches", ["match_run_id", "status"])
    op.create_index("ix_feature_matches_run_score", "feature_matches", ["match_run_id", "overall_score"])


def downgrade() -> None:
    op.drop_table("feature_matches")
    op.drop_table("match_runs")
