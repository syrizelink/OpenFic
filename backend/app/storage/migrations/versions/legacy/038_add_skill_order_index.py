"""add order_index to skills table and allow duplicate empty skill_id

Revision ID: 038
Revises: 037
Create Date: 2026-05-17

允许 skill_id 为空（新建时不强制填写），并添加 order_index 支持拖拽排序。
移除 skill_id 的 UNIQUE 约束，改为应用层校验非空 skill_id 的唯一性。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 使用 batch mode 重建表：添加 order_index 列并移除 skill_id 的 unique 约束
    with op.batch_alter_table(
        "skills",
        schema=None,
        recreate="always",
        table_args=(
            sa.PrimaryKeyConstraint("id"),
        ),
    ) as batch_op:
        batch_op.add_column(
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "skills",
        schema=None,
        recreate="always",
        table_args=(
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("skill_id"),
        ),
    ) as batch_op:
        batch_op.drop_column("order_index")
