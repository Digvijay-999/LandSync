"""Add human review audit table and review status to feature matches

Revision ID: 0006_match_reviews
Revises: 0005_candidate_ranking
Create Date: 2026-09-27 10:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0006_match_reviews"
down_revision: Union[str, None] = "0005_candidate_ranking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add review_status column to feature_matches
    op.add_column(
        "feature_matches",
        sa.Column(
            "review_status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
    )
    op.create_index(
        "ix_feature_matches_run_review_status",
        "feature_matches",
        ["match_run_id", "review_status"],
    )

    # 2. Create match_reviews audit history table
    op.create_table(
        "match_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "feature_match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feature_matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("ix_match_reviews_id", "match_reviews", ["id"])
    op.create_index("ix_match_reviews_feature_match_id", "match_reviews", ["feature_match_id"])
    op.create_index("ix_match_reviews_decision", "match_reviews", ["decision"])
    op.create_index(
        "ix_match_reviews_match_created",
        "match_reviews",
        ["feature_match_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("match_reviews")
    op.drop_index("ix_feature_matches_run_review_status", table_name="feature_matches")
    op.drop_column("feature_matches", "review_status")
