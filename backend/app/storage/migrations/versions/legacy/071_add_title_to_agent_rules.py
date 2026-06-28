"""add title to agent rules

Revision ID: 071
Revises: 070
Create Date: 2026-06-24 15:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "071"
down_revision: Union[str, None] = "070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("agent_rules") as batch_op:
        batch_op.add_column(sa.Column("title", sa.Text(), nullable=True))

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE agent_rules
            SET title = content
            WHERE title IS NULL OR trim(title) = ''
            """
        )
    )

    with op.batch_alter_table("agent_rules") as batch_op:
        batch_op.alter_column(
            "title",
            existing_type=sa.Text(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_rules") as batch_op:
        batch_op.drop_column("title")
