"""Add candidate ranking, roles, score_gap, and quality metrics

Revision ID: 0005_candidate_ranking
Revises: 0004_matching
Create Date: 2026-09-27 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_candidate_ranking"
down_revision: Union[str, None] = "0004_matching"

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add quality_metrics to match_runs
    op.add_column(
        "match_runs",
        sa.Column("quality_metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    # 2. Add ranking and role columns to feature_matches
    op.add_column(
        "feature_matches",
        sa.Column("rank", sa.Integer(), nullable=True),
    )
    op.add_column(
        "feature_matches",
        sa.Column("is_best_candidate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "feature_matches",
        sa.Column("candidate_role", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "feature_matches",
        sa.Column("score_gap", sa.Float(), nullable=True),
    )
    op.add_column(
        "feature_matches",
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    # 3. Create indexes for efficient querying
    op.create_index(
        "ix_feature_matches_run_best",
        "feature_matches",
        ["match_run_id", "is_best_candidate"],
    )
    op.create_index(
        "ix_feature_matches_run_role",
        "feature_matches",
        ["match_run_id", "candidate_role"],
    )
    op.create_index(
        "ix_feature_matches_source_rank",
        "feature_matches",
        ["source_feature_id", "rank"],
    )


def downgrade() -> None:
    op.drop_index("ix_feature_matches_source_rank", table_name="feature_matches")
    op.drop_index("ix_feature_matches_run_role", table_name="feature_matches")
    op.drop_index("ix_feature_matches_run_best", table_name="feature_matches")

    op.drop_column("feature_matches", "candidate_count")
    op.drop_column("feature_matches", "score_gap")
    op.drop_column("feature_matches", "candidate_role")
    op.drop_column("feature_matches", "is_best_candidate")
    op.drop_column("feature_matches", "rank")

    op.drop_column("match_runs", "quality_metrics")
