"""Add assistant_documents table for RAG vector search

Revision ID: 0010_assistant_documents
Revises: 0009_attribute_conflicts
Create Date: 2026-09-30 14:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0010_assistant_documents"
down_revision: Union[str, None] = "0009_attribute_conflicts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create assistant_documents table
    op.create_table(
        "assistant_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_category", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "doc_metadata",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "embedding",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
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

    # 3. Create indexes
    op.create_index("ix_assistant_documents_id", "assistant_documents", ["id"])
    op.create_index("ix_assistant_documents_project_id", "assistant_documents", ["project_id"])
    op.create_index("ix_assistant_documents_document_category", "assistant_documents", ["document_category"])
    op.create_index("ix_assistant_documents_entity_id", "assistant_documents", ["entity_id"])
    op.create_index(
        "ix_assistant_docs_project_category",
        "assistant_documents",
        ["project_id", "document_category"],
    )
    op.create_index(
        "ix_assistant_docs_project_entity",
        "assistant_documents",
        ["project_id", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_docs_project_entity", table_name="assistant_documents")
    op.drop_index("ix_assistant_docs_project_category", table_name="assistant_documents")
    op.drop_index("ix_assistant_documents_entity_id", table_name="assistant_documents")
    op.drop_index("ix_assistant_documents_document_category", table_name="assistant_documents")
    op.drop_index("ix_assistant_documents_project_id", table_name="assistant_documents")
    op.drop_index("ix_assistant_documents_id", table_name="assistant_documents")
    op.drop_table("assistant_documents")
