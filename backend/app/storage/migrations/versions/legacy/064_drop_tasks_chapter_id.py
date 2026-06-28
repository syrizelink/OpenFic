"""drop tasks.chapter_id

Revision ID: 064
Revises: 063
Create Date: 2026-06-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "064"
down_revision: Union[str, None] = "063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_index("ix_tasks_chapter_id")
        batch_op.drop_column("chapter_id")


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("chapter_id", sa.String(), nullable=False, server_default="")
        )
        batch_op.create_index("ix_tasks_chapter_id", ["chapter_id"], unique=False)