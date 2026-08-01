"""add agent attachments

Revision ID: 1015
Revises: 1014
Create Date: 2026-08-01 15:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1015"
down_revision: Union[str, Sequence[str], None] = "1014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_attachments",
        sa.Column("id", sa.String(length=21), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("storage_name", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=50), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_name"),
    )
    op.create_index("ix_agent_attachments_session_id", "agent_attachments", ["session_id"])
    op.create_index("ix_agent_attachments_task_id", "agent_attachments", ["task_id"])
    op.create_index("ix_agent_attachments_project_id", "agent_attachments", ["project_id"])
    op.create_index("ix_agent_attachments_created_at", "agent_attachments", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_attachments_created_at", table_name="agent_attachments")
    op.drop_index("ix_agent_attachments_project_id", table_name="agent_attachments")
    op.drop_index("ix_agent_attachments_task_id", table_name="agent_attachments")
    op.drop_index("ix_agent_attachments_session_id", table_name="agent_attachments")
    op.drop_table("agent_attachments")
