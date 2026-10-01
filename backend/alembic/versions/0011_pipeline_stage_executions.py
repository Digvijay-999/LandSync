"""Add pipeline_stage_executions table for persisting workflow stage states

Revision ID: 0011_pipeline_stage_executions
Revises: 0010_assistant_documents
Create Date: 2026-10-01 16:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0011_pipeline_stage_executions"
down_revision: Union[str, None] = "0010_assistant_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_stage_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage_number", sa.Integer(), nullable=False),
        sa.Column("stage_id", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="idle"),
        sa.Column("inputs", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("results", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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

    op.create_index("ix_pipeline_stage_executions_id", "pipeline_stage_executions", ["id"])
    op.create_index("ix_pipeline_stage_executions_project_id", "pipeline_stage_executions", ["project_id"])
    op.create_index("ix_pipeline_stage_executions_stage_id", "pipeline_stage_executions", ["stage_id"])
    op.create_index("ix_pipeline_stage_executions_stage_number", "pipeline_stage_executions", ["stage_number"])
    op.create_index(
        "ix_pipeline_stage_proj_stage",
        "pipeline_stage_executions",
        ["project_id", "stage_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_stage_proj_stage", table_name="pipeline_stage_executions")
    op.drop_index("ix_pipeline_stage_executions_stage_number", table_name="pipeline_stage_executions")
    op.drop_index("ix_pipeline_stage_executions_stage_id", table_name="pipeline_stage_executions")
    op.drop_index("ix_pipeline_stage_executions_project_id", table_name="pipeline_stage_executions")
    op.drop_index("ix_pipeline_stage_executions_id", table_name="pipeline_stage_executions")
    op.drop_table("pipeline_stage_executions")
