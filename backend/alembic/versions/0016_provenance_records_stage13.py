"""Create provenance_records table for Stage 13 Provenance & Lineage

Revision ID: 0016_provenance_records_stage13
Revises: 0015_unified_records_stage12
Create Date: 2026-10-02 18:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0016_provenance_records_stage13"
down_revision: Union[str, None] = "0015_unified_records_stage12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provenance_records",
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
        sa.Column("harmonized_record_id", sa.String(length=255), nullable=False),
        sa.Column("record_identifier", sa.String(length=150), nullable=False),
        sa.Column("source_dataset_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source_feature_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source_record_identifiers", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "feature_match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feature_matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("matched_record_id", sa.String(length=255), nullable=True),
        sa.Column("conflict_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "validation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_results.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "human_review_decision_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("human_review_decisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("confidence_bucket", sa.String(length=50), nullable=True),
        sa.Column("resolution_status", sa.String(length=50), nullable=False, server_default="UNIFIED"),
        sa.Column("lineage_completeness_pct", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("lineage_status", sa.String(length=30), nullable=False, server_default="COMPLETE"),
        sa.Column("missing_stages", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("lineage_graph", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("metadata_trail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "unified_land_record_id", name="uq_project_unified_record_provenance"),
    )

    op.create_index("ix_provenance_records_id", "provenance_records", ["id"])
    op.create_index("ix_provenance_records_project_id", "provenance_records", ["project_id"])
    op.create_index("ix_provenance_records_unified_land_record_id", "provenance_records", ["unified_land_record_id"])
    op.create_index("ix_provenance_records_harmonized_record_id", "provenance_records", ["harmonized_record_id"])
    op.create_index("ix_provenance_records_record_identifier", "provenance_records", ["record_identifier"])
    op.create_index("ix_provenance_records_resolution_status", "provenance_records", ["resolution_status"])
    op.create_index("ix_provenance_records_lineage_status", "provenance_records", ["lineage_status"])
    op.create_index("ix_provenance_records_project_created", "provenance_records", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_provenance_records_project_created", table_name="provenance_records")
    op.drop_index("ix_provenance_records_lineage_status", table_name="provenance_records")
    op.drop_index("ix_provenance_records_resolution_status", table_name="provenance_records")
    op.drop_index("ix_provenance_records_record_identifier", table_name="provenance_records")
    op.drop_index("ix_provenance_records_harmonized_record_id", table_name="provenance_records")
    op.drop_index("ix_provenance_records_unified_land_record_id", table_name="provenance_records")
    op.drop_index("ix_provenance_records_project_id", table_name="provenance_records")
    op.drop_index("ix_provenance_records_id", table_name="provenance_records")
    op.drop_table("provenance_records")
