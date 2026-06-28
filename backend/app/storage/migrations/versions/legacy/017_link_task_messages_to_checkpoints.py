"""link task messages to checkpoints and reset related data

Revision ID: 017_link_task_messages_to_checkpoints
Revises: 016
Create Date: 2026-04-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "017_link_task_messages_to_checkpoints"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM commits")
    op.execute("DELETE FROM revisions")
    op.execute("DELETE FROM artifacts")
    op.execute("DELETE FROM tasks")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("current_revision_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("current_message_id", sa.String(), nullable=True))
        batch_op.create_index("ix_tasks_current_revision_id", ["current_revision_id"], unique=False)
        batch_op.create_index("ix_tasks_current_message_id", ["current_message_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_tasks_current_revision_id_revisions",
            "revisions",
            ["current_revision_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("fk_tasks_current_revision_id_revisions", type_="foreignkey")
        batch_op.drop_index("ix_tasks_current_message_id")
        batch_op.drop_index("ix_tasks_current_revision_id")
        batch_op.drop_column("current_message_id")
        batch_op.drop_column("current_revision_id")
