"""Add source_features and canonical_features tables with PostGIS GIST indexes

Revision ID: 0003_features
Revises: 0002_dataset_and_versions
Create Date: 2026-09-27 02:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = "0003_features"
down_revision: Union[str, None] = "0002_dataset_and_versions"

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create source_features table
    op.create_table(
        "source_features",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "dataset_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_feature_id", sa.String(length=255), nullable=True),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("source_crs", sa.String(length=100), nullable=False, server_default="EPSG:4326"),
        sa.Column("geometry_type", sa.String(length=50), nullable=False, server_default="Unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_source_features_id"), "source_features", ["id"], unique=False)
    op.create_index(op.f("ix_source_features_dataset_version_id"), "source_features", ["dataset_version_id"], unique=False)
    op.create_index(op.f("ix_source_features_source_feature_id"), "source_features", ["source_feature_id"], unique=False)
    # GIST spatial index
    op.create_index("idx_source_features_geometry", "source_features", ["geometry"], postgresql_using="gist")

    # 2. Create canonical_features table
    op.create_table(
        "canonical_features",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "dataset_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_features.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("geometry_type", sa.String(length=50), nullable=False, server_default="Unknown"),
        sa.Column("canonical_properties", sa.JSON(), nullable=False),
        sa.Column("source_crs", sa.String(length=100), nullable=False),
        sa.Column("target_crs", sa.String(length=100), nullable=False, server_default="EPSG:4326"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_canonical_features_id"), "canonical_features", ["id"], unique=False)
    op.create_index(op.f("ix_canonical_features_dataset_version_id"), "canonical_features", ["dataset_version_id"], unique=False)
    op.create_index(op.f("ix_canonical_features_source_feature_id"), "canonical_features", ["source_feature_id"], unique=False)
    # GIST spatial index
    op.create_index("idx_canonical_features_geometry", "canonical_features", ["geometry"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_index("idx_canonical_features_geometry", table_name="canonical_features", postgresql_using="gist")
    op.drop_index(op.f("ix_canonical_features_source_feature_id"), table_name="canonical_features")
    op.drop_index(op.f("ix_canonical_features_dataset_version_id"), table_name="canonical_features")
    op.drop_index(op.f("ix_canonical_features_id"), table_name="canonical_features")
    op.drop_table("canonical_features")

    op.drop_index("idx_source_features_geometry", table_name="source_features", postgresql_using="gist")
    op.drop_index(op.f("ix_source_features_source_feature_id"), table_name="source_features")
    op.drop_index(op.f("ix_source_features_dataset_version_id"), table_name="source_features")
    op.drop_index(op.f("ix_source_features_id"), table_name="source_features")
    op.drop_table("source_features")
