"""Add human_review_decisions table for Stage 11 Human Review Adjudication

Revision ID: 0014_human_review_decisions
Revises: 0013_validation_results
Create Date: 2026-10-02 02:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0014_human_review_decisions"
down_revision: Union[str, None] = "0013_validation_results"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "human_review_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("harmonized_record_id", sa.String(length=255), nullable=False),
        sa.Column(
            "source_feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_features.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "candidate_feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_features.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "feature_match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feature_matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("adjudication_status", sa.String(length=30), nullable=False, server_default="RESOLVED"),
        sa.Column("reviewer_name", sa.String(length=100), nullable=False, server_default="Lead GIS Adjudicator"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("authoritative_geometry_source", sa.String(length=50), nullable=True),
        sa.Column("authoritative_attributes", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("previous_state", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("resulting_state", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("override_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_human_review_decisions_id",
        "human_review_decisions",
        ["id"],
    )
    op.create_index(
        "ix_human_review_decisions_project_id",
        "human_review_decisions",
        ["project_id"],
    )
    op.create_index(
        "ix_human_review_decisions_record_id",
        "human_review_decisions",
        ["harmonized_record_id"],
    )
    op.create_index(
        "ix_human_review_decisions_action",
        "human_review_decisions",
        ["action"],
    )
    op.create_index(
        "ix_human_review_decisions_status",
        "human_review_decisions",
        ["adjudication_status"],
    )
    op.create_index(
        "ix_human_review_decisions_idempotency_key",
        "human_review_decisions",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_human_review_project_status",
        "human_review_decisions",
        ["project_id", "adjudication_status"],
    )
    op.create_index(
        "ix_human_review_project_action",
        "human_review_decisions",
        ["project_id", "action"],
    )


def downgrade() -> None:
    op.drop_table("human_review_decisions")
