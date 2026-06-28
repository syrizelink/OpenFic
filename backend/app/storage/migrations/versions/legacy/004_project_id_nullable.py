"""make_project_id_nullable

让 world_info 表的 project_id 字段可为空，支持创建独立世界书。

Revision ID: 004
Revises: 003
Create Date: 2024-12-29
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将 project_id 改为可空字段。"""
    # SQLite 不支持直接修改列，需要重建表
    # 但对于这种情况，SQLite 允许 NULL 值即使列定义为 NOT NULL
    # 因为 SQLModel 会在 Python 层面处理这个逻辑
    # 这里我们使用 batch_alter_table 来安全修改
    with op.batch_alter_table("world_info") as batch_op:
        batch_op.alter_column(
            "project_id",
            nullable=True,
        )


def downgrade() -> None:
    """将 project_id 改回非空字段。"""
    with op.batch_alter_table("world_info") as batch_op:
        batch_op.alter_column(
            "project_id",
            nullable=False,
        )
