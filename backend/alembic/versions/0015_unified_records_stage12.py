"""Add Stage 12 Unified Record synthesis fields and constraints to unified_land_records

Revision ID: 0015_unified_records_stage12
Revises: 0014_human_review_decisions
Create Date: 2026-10-02 17:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0015_unified_records_stage12"
down_revision: Union[str, None] = "0014_human_review_decisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add Stage 12 authoritative synthesis columns
    op.add_column(
        "unified_land_records",
        sa.Column("harmonized_record_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "unified_land_records",
        sa.Column("source_a_reference", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "unified_land_records",
        sa.Column("source_b_reference", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "unified_land_records",
        sa.Column("geometry_source", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "unified_land_records",
        sa.Column("land_use", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "unified_land_records",
        sa.Column("mutation_status", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "unified_land_records",
        sa.Column("risk_level", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "unified_land_records",
        sa.Column("confidence_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "unified_land_records",
        sa.Column("validation_status", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "unified_land_records",
        sa.Column("human_review_decision", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "unified_land_records",
        sa.Column("resolution_status", sa.String(length=50), nullable=False, server_default=sa.text("'UNIFIED'")),
    )
    op.add_column(
        "unified_land_records",
        sa.Column("metadata_trail", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    # 2. Add indexes and unique constraint
    op.create_index(
        op.f("ix_unified_land_records_harmonized_record_id"),
        "unified_land_records",
        ["harmonized_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_unified_records_project_resolution",
        "unified_land_records",
        ["project_id", "resolution_status"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_project_harmonized_record_id",
        "unified_land_records",
        ["project_id", "harmonized_record_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_project_harmonized_record_id", "unified_land_records", type_="unique")
    op.drop_index("ix_unified_records_project_resolution", table_name="unified_land_records")
    op.drop_index(op.f("ix_unified_land_records_harmonized_record_id"), table_name="unified_land_records")

    op.drop_column("unified_land_records", "metadata_trail")
    op.drop_column("unified_land_records", "resolution_status")
    op.drop_column("unified_land_records", "human_review_decision")
    op.drop_column("unified_land_records", "validation_status")
    op.drop_column("unified_land_records", "confidence_score")
    op.drop_column("unified_land_records", "risk_level")
    op.drop_column("unified_land_records", "mutation_status")
    op.drop_column("unified_land_records", "land_use")
    op.drop_column("unified_land_records", "geometry_source")
    op.drop_column("unified_land_records", "source_b_reference")
    op.drop_column("unified_land_records", "source_a_reference")
    op.drop_column("unified_land_records", "harmonized_record_id")
