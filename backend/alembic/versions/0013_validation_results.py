"""Add validation_results table for Stage 09 Validation

Revision ID: 0013_validation_results
Revises: 0012_geospatial_conflicts
Create Date: 2026-10-02 01:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0013_validation_results"
down_revision: Union[str, None] = "0012_geospatial_conflicts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_results",
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
        sa.Column("source_identifier", sa.String(length=100), nullable=False),
        sa.Column("candidate_identifier", sa.String(length=100), nullable=False),
        sa.Column("overall_status", sa.String(length=20), nullable=False, server_default="PASS"),
        sa.Column("geometry_validity_status", sa.String(length=20), nullable=False, server_default="PASS"),
        sa.Column("topology_status", sa.String(length=20), nullable=False, server_default="PASS"),
        sa.Column("area_status", sa.String(length=20), nullable=False, server_default="PASS"),
        sa.Column("semantic_status", sa.String(length=20), nullable=False, server_default="PASS"),
        sa.Column("conflict_status", sa.String(length=20), nullable=False, server_default="PASS"),
        sa.Column("failure_reasons", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("warning_reasons", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("geometry_metrics", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("topology_metrics", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("area_metrics", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("semantic_metrics", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("conflict_metrics", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_validation_results_id", "validation_results", ["id"])
    op.create_index("ix_validation_results_project_id", "validation_results", ["project_id"])
    op.create_index("ix_validation_results_harmonized_record_id", "validation_results", ["harmonized_record_id"])
    op.create_index("ix_validation_results_source_feature_id", "validation_results", ["source_feature_id"])
    op.create_index("ix_validation_results_candidate_feature_id", "validation_results", ["candidate_feature_id"])
    op.create_index("ix_validation_results_overall_status", "validation_results", ["overall_status"])
    op.create_index("ix_validation_results_idempotency_key", "validation_results", ["idempotency_key"], unique=True)
    op.create_index(
        "ix_validation_results_proj_status",
        "validation_results",
        ["project_id", "overall_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_validation_results_proj_status", table_name="validation_results")
    op.drop_index("ix_validation_results_idempotency_key", table_name="validation_results")
    op.drop_index("ix_validation_results_overall_status", table_name="validation_results")
    op.drop_index("ix_validation_results_candidate_feature_id", table_name="validation_results")
    op.drop_index("ix_validation_results_source_feature_id", table_name="validation_results")
    op.drop_index("ix_validation_results_harmonized_record_id", table_name="validation_results")
    op.drop_index("ix_validation_results_project_id", table_name="validation_results")
    op.drop_index("ix_validation_results_id", table_name="validation_results")
    op.drop_table("validation_results")
