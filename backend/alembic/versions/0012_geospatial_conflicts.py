"""Add geospatial_conflicts table for Stage 08 Conflict Detection

Revision ID: 0012_geospatial_conflicts
Revises: 0011_pipeline_stage_executions
Create Date: 2026-10-02 00:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0012_geospatial_conflicts"
down_revision: Union[str, None] = "0011_pipeline_stage_executions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "geospatial_conflicts",
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
        sa.Column("conflict_type", sa.String(length=60), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="ATTRIBUTE"),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="MEDIUM"),
        sa.Column("severity_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="OPEN"),
        sa.Column("source_a", sa.String(length=150), nullable=False),
        sa.Column("source_b", sa.String(length=150), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("value_a", sa.Text(), nullable=True),
        sa.Column("value_b", sa.Text(), nullable=True),
        sa.Column("normalized_value_a", sa.Text(), nullable=True),
        sa.Column("normalized_value_b", sa.Text(), nullable=True),
        sa.Column("discrepancy_value", sa.Text(), nullable=True),
        sa.Column("discrepancy_percentage", sa.Float(), nullable=True),
        sa.Column("detection_rule", sa.String(length=100), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("evidence", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("geometry_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
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

    op.create_index("ix_geospatial_conflicts_id", "geospatial_conflicts", ["id"])
    op.create_index("ix_geospatial_conflicts_project_id", "geospatial_conflicts", ["project_id"])
    op.create_index("ix_geospatial_conflicts_harmonized_record_id", "geospatial_conflicts", ["harmonized_record_id"])
    op.create_index("ix_geospatial_conflicts_source_feature_id", "geospatial_conflicts", ["source_feature_id"])
    op.create_index("ix_geospatial_conflicts_candidate_feature_id", "geospatial_conflicts", ["candidate_feature_id"])
    op.create_index("ix_geospatial_conflicts_conflict_type", "geospatial_conflicts", ["conflict_type"])
    op.create_index("ix_geospatial_conflicts_category", "geospatial_conflicts", ["category"])
    op.create_index("ix_geospatial_conflicts_severity", "geospatial_conflicts", ["severity"])
    op.create_index("ix_geospatial_conflicts_status", "geospatial_conflicts", ["status"])
    op.create_index("ix_geospatial_conflicts_field_name", "geospatial_conflicts", ["field_name"])
    op.create_index("ix_geospatial_conflicts_idempotency_key", "geospatial_conflicts", ["idempotency_key"], unique=True)
    op.create_index(
        "ix_geospatial_conflicts_proj_status",
        "geospatial_conflicts",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_geospatial_conflicts_proj_severity",
        "geospatial_conflicts",
        ["project_id", "severity"],
    )


def downgrade() -> None:
    op.drop_index("ix_geospatial_conflicts_proj_severity", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_proj_status", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_idempotency_key", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_field_name", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_status", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_severity", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_category", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_conflict_type", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_candidate_feature_id", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_source_feature_id", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_harmonized_record_id", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_project_id", table_name="geospatial_conflicts")
    op.drop_index("ix_geospatial_conflicts_id", table_name="geospatial_conflicts")
    op.drop_table("geospatial_conflicts")
