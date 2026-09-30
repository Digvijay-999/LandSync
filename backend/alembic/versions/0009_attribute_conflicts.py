"""Add attribute_conflicts and conflict_resolutions tables

Revision ID: 0009_attribute_conflicts
Revises: 0008_provenance_audit_events
Create Date: 2026-09-29 16:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0009_attribute_conflicts"
down_revision: Union[str, None] = "0008_provenance_audit_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create attribute_conflicts table (initially without resolution_id FK)
    op.create_table(
        "attribute_conflicts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unified_land_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("unified_land_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attribute_name", sa.String(length=100), nullable=False),
        sa.Column("conflict_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default=sa.text("'MEDIUM'")),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'UNRESOLVED'")),
        sa.Column(
            "detected_values",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("resolution_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.UniqueConstraint("unified_land_record_id", "attribute_name", name="uq_record_attribute_conflict"),
    )

    op.create_index("ix_attribute_conflicts_id", "attribute_conflicts", ["id"])
    op.create_index("ix_attribute_conflicts_project_id", "attribute_conflicts", ["project_id"])
    op.create_index("ix_attribute_conflicts_unified_land_record_id", "attribute_conflicts", ["unified_land_record_id"])
    op.create_index("ix_attribute_conflicts_attribute_name", "attribute_conflicts", ["attribute_name"])
    op.create_index("ix_attribute_conflicts_conflict_type", "attribute_conflicts", ["conflict_type"])
    op.create_index("ix_attribute_conflicts_severity", "attribute_conflicts", ["severity"])
    op.create_index("ix_attribute_conflicts_status", "attribute_conflicts", ["status"])
    op.create_index("ix_attribute_conflicts_created_at", "attribute_conflicts", ["created_at"])
    op.create_index("ix_attribute_conflicts_project_status", "attribute_conflicts", ["project_id", "status"])
    op.create_index("ix_attribute_conflicts_record_status", "attribute_conflicts", ["unified_land_record_id", "status"])

    # 2. Create conflict_resolutions table
    op.create_table(
        "conflict_resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "conflict_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attribute_conflicts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resolution_type", sa.String(length=50), nullable=False),
        sa.Column(
            "selected_source_feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_features.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("selected_source_role", sa.String(length=50), nullable=True),
        sa.Column("resolved_value", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("resolved_by", sa.String(length=100), nullable=True),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_conflict_resolutions_id", "conflict_resolutions", ["id"])
    op.create_index("ix_conflict_resolutions_conflict_id", "conflict_resolutions", ["conflict_id"])
    op.create_index("ix_conflict_resolutions_selected_source_feature_id", "conflict_resolutions", ["selected_source_feature_id"])

    # 3. Add FK from attribute_conflicts.resolution_id -> conflict_resolutions.id
    op.create_foreign_key(
        "fk_attribute_conflicts_resolution_id",
        "attribute_conflicts",
        "conflict_resolutions",
        ["resolution_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_attribute_conflicts_resolution_id", "attribute_conflicts", type_="foreignkey")
    op.drop_table("conflict_resolutions")
    op.drop_table("attribute_conflicts")
