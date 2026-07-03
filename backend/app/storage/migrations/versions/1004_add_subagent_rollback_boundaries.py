"""add subagent rollback boundaries

Revision ID: 1004
Revises: 1003
Create Date: 2026-07-03 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1004"
down_revision: Union[str, Sequence[str], None] = "1003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("agent_child_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_revision_id", sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f("ix_agent_child_runs_parent_revision_id"), ["parent_revision_id"], unique=False)

    with op.batch_alter_table("agent_child_run_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_revision_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("child_user_message_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("child_user_message_seq", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("pre_request_checkpoint_id", sa.String(length=128), nullable=True))
        batch_op.create_index(batch_op.f("ix_agent_child_run_requests_parent_revision_id"), ["parent_revision_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_agent_child_run_requests_child_user_message_id"), ["child_user_message_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_agent_child_run_requests_child_user_message_seq"), ["child_user_message_seq"], unique=False)
        batch_op.create_index(batch_op.f("ix_agent_child_run_requests_pre_request_checkpoint_id"), ["pre_request_checkpoint_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("agent_child_run_requests", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_child_run_requests_pre_request_checkpoint_id"))
        batch_op.drop_index(batch_op.f("ix_agent_child_run_requests_child_user_message_seq"))
        batch_op.drop_index(batch_op.f("ix_agent_child_run_requests_child_user_message_id"))
        batch_op.drop_index(batch_op.f("ix_agent_child_run_requests_parent_revision_id"))
        batch_op.drop_column("pre_request_checkpoint_id")
        batch_op.drop_column("child_user_message_seq")
        batch_op.drop_column("child_user_message_id")
        batch_op.drop_column("parent_revision_id")

    with op.batch_alter_table("agent_child_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_child_runs_parent_revision_id"))
        batch_op.drop_column("parent_revision_id")
