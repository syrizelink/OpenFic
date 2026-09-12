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
    Mengubah nama Tionghoa pada tabel prompt_chains menjadi format ID
    - mode_name: "Asisten Kreatif" -> "assistant"
    - task_name: "Chat" -> "chat"
    """
    conn = op.get_bind()
    
    # Memperbarui data yang ada
    conn.execute(
        sa.text("""
            UPDATE prompt_chains 
            SET mode_name = 'assistant', task_name = 'chat'
            WHERE mode_name = 'Asisten Kreatif' AND task_name = 'Chat'
        """)
    )


def downgrade() -> None:
    """
    Mengembalikan ke nama Tionghoa
    """
    conn = op.get_bind()
    
    conn.execute(
        sa.text("""
            UPDATE prompt_chains 
            SET mode_name = 'Asisten Kreatif', task_name = 'Chat'
            WHERE mode_name = 'assistant' AND task_name = 'chat'
        """)
    )
