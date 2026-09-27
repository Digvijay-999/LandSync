"""Add dataset and dataset_version tables

Revision ID: 0002_dataset_and_versions
Revises: 0001_initial_project_model
Create Date: 2026-09-27 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_dataset_and_versions"
down_revision: Union[str, None] = "0001_initial_project_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create datasets table
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_format", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), server_default="vector", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="ready", nullable=False),
        sa.Column("feature_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("geometry_type", sa.String(length=100), server_default="Unknown", nullable=False),
        sa.Column("detected_crs", sa.String(length=100), nullable=True),
        sa.Column("bounding_box", sa.JSON(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("profile_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_datasets_id"), "datasets", ["id"], unique=False)
    op.create_index(op.f("ix_datasets_project_id"), "datasets", ["project_id"], unique=False)
    op.create_index(op.f("ix_datasets_name"), "datasets", ["name"], unique=False)

    # 2. Create dataset_versions table
    op.create_table(
        "dataset_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("profile_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_dataset_versions_id"), "dataset_versions", ["id"], unique=False)
    op.create_index(op.f("ix_dataset_versions_dataset_id"), "dataset_versions", ["dataset_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dataset_versions_dataset_id"), table_name="dataset_versions")
    op.drop_index(op.f("ix_dataset_versions_id"), table_name="dataset_versions")
    op.drop_table("dataset_versions")

    op.drop_index(op.f("ix_datasets_name"), table_name="datasets")
    op.drop_index(op.f("ix_datasets_project_id"), table_name="datasets")
    op.drop_index(op.f("ix_datasets_id"), table_name="datasets")
    op.drop_table("datasets")
