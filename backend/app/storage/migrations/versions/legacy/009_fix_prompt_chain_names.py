"""fix prompt chain names

Revision ID: 009
Revises: 008
Create Date: 2026-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    将 prompt_chains 表中的中文名称修改为ID格式
    - mode_name: "创作助手" -> "assistant"
    - task_name: "Chat" -> "chat"
    """
    conn = op.get_bind()
    
    # 更新现有数据
    conn.execute(
        sa.text("""
            UPDATE prompt_chains 
            SET mode_name = 'assistant', task_name = 'chat'
            WHERE mode_name = '创作助手' AND task_name = 'Chat'
        """)
    )


def downgrade() -> None:
    """
    回滚到中文名称
    """
    conn = op.get_bind()
    
    conn.execute(
        sa.text("""
            UPDATE prompt_chains 
            SET mode_name = '创作助手', task_name = 'Chat'
            WHERE mode_name = 'assistant' AND task_name = 'chat'
        """)
    )
