"""Add provenance_events table for audit trails and export tracking

Revision ID: 0008_provenance_audit_events
Revises: 0007_unified_land_records
Create Date: 2026-09-27 11:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0008_provenance_audit_events"
down_revision: Union[str, None] = "0007_unified_land_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provenance_events",
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
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_provenance_events_id", "provenance_events", ["id"])
    op.create_index("ix_provenance_events_project_id", "provenance_events", ["project_id"])
    op.create_index("ix_provenance_events_unified_land_record_id", "provenance_events", ["unified_land_record_id"])
    op.create_index("ix_provenance_events_event_type", "provenance_events", ["event_type"])
    op.create_index("ix_provenance_events_created_at", "provenance_events", ["created_at"])
    op.create_index("ix_provenance_events_project_created", "provenance_events", ["project_id", "created_at"])
    op.create_index("ix_provenance_events_record_created", "provenance_events", ["unified_land_record_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_provenance_events_record_created", table_name="provenance_events")
    op.drop_index("ix_provenance_events_project_created", table_name="provenance_events")
    op.drop_index("ix_provenance_events_created_at", table_name="provenance_events")
    op.drop_index("ix_provenance_events_event_type", table_name="provenance_events")
    op.drop_index("ix_provenance_events_unified_land_record_id", table_name="provenance_events")
    op.drop_index("ix_provenance_events_project_id", table_name="provenance_events")
    op.drop_index("ix_provenance_events_id", table_name="provenance_events")
    op.drop_table("provenance_events")
