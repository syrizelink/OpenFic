"""Add tasks table

Revision ID: 012
Revises: 011
Create Date: 2025-02-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 删除多余的表（如果存在）
    op.execute("DROP TABLE IF EXISTS ai_chat_messages")
    op.execute("DROP TABLE IF EXISTS ai_tasks")
    
    # 创建 tasks 表
    op.create_table(
        'tasks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=False),
        sa.Column('chapter_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('mode', sa.String(length=20), nullable=False),
        sa.Column('messages', sa.String(), nullable=False, server_default='[]'),
        sa.Column('is_favorited', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ),
    )
    
    # 创建索引
    op.create_index(op.f('ix_tasks_project_id'), 'tasks', ['project_id'], unique=False)
    op.create_index(op.f('ix_tasks_chapter_id'), 'tasks', ['chapter_id'], unique=False)
    op.create_index(op.f('ix_tasks_mode'), 'tasks', ['mode'], unique=False)
    op.create_index(op.f('ix_tasks_is_favorited'), 'tasks', ['is_favorited'], unique=False)


def downgrade() -> None:
    # 删除索引
    op.drop_index(op.f('ix_tasks_is_favorited'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_mode'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_chapter_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_project_id'), table_name='tasks')
    
    # 删除表
    op.drop_table('tasks')