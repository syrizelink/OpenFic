"""add extracted content metadata to agent attachments

Revision ID: 1022
Revises: 1021
Create Date: 2026-09-20 16:50:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1022"
down_revision: Union[str, Sequence[str], None] = "1021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_attachments") as batch_op:
        batch_op.add_column(sa.Column("content", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("content_length", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.alter_column(
            "width",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.alter_column(
            "height",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_attachments") as batch_op:
        batch_op.drop_column("line_count")
        batch_op.drop_column("content_length")
        batch_op.drop_column("content")
        batch_op.alter_column(
            "width",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "height",
            existing_type=sa.Integer(),
            nullable=False,
        )
