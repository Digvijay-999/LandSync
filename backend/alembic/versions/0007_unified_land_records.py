"""Add unified_land_records and unified_land_record_sources tables

Revision ID: 0007_unified_land_records
Revises: 0006_match_reviews
Create Date: 2026-09-27 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = "0007_unified_land_records"
down_revision: Union[str, None] = "0006_match_reviews"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create unified_land_records table
    op.create_table(
        "unified_land_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("record_identifier", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column(
            "canonical_geometry",
            geoalchemy2.types.Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column(
            "geometry_source_feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_features.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("geometry_source_role", sa.String(length=50), nullable=True),
        sa.Column("area", sa.Float(), nullable=True),
        sa.Column("canonical_attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "record_identifier", name="uq_project_unified_record_identifier"),
    )
    op.create_index(op.f("ix_unified_land_records_id"), "unified_land_records", ["id"], unique=False)
    op.create_index(op.f("ix_unified_land_records_project_id"), "unified_land_records", ["project_id"], unique=False)
    op.create_index(op.f("ix_unified_land_records_record_identifier"), "unified_land_records", ["record_identifier"], unique=False)
    op.create_index(op.f("ix_unified_land_records_status"), "unified_land_records", ["status"], unique=False)
    op.create_index(op.f("ix_unified_land_records_geometry_source_feature_id"), "unified_land_records", ["geometry_source_feature_id"], unique=False)
    op.create_index("ix_unified_records_project_status", "unified_land_records", ["project_id", "status"], unique=False)
    op.create_index("idx_unified_land_records_canonical_geometry", "unified_land_records", ["canonical_geometry"], postgresql_using="gist")

    # 2. Create unified_land_record_sources table
    op.create_table(
        "unified_land_record_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "unified_land_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("unified_land_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_features.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "feature_match_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("feature_matches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_role", sa.String(length=50), nullable=False, server_default=sa.text("'OTHER'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("unified_land_record_id", "feature_id", name="uq_unified_record_source_feature"),
    )
    op.create_index(op.f("ix_unified_land_record_sources_id"), "unified_land_record_sources", ["id"], unique=False)
    op.create_index(op.f("ix_unified_land_record_sources_unified_land_record_id"), "unified_land_record_sources", ["unified_land_record_id"], unique=False)
    op.create_index(op.f("ix_unified_land_record_sources_feature_id"), "unified_land_record_sources", ["feature_id"], unique=False)
    op.create_index(op.f("ix_unified_land_record_sources_feature_match_id"), "unified_land_record_sources", ["feature_match_id"], unique=False)


def downgrade() -> None:
    op.drop_table("unified_land_record_sources")
    op.drop_table("unified_land_records")
