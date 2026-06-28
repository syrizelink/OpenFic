"""replace clarifier with explorer in active agent config

Revision ID: 054
Revises: 053
Create Date: 2026-06-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "054"
down_revision: Union[str, None] = "053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE agent_definitions
            SET key = 'explorer',
                display_name = 'Explorer',
                prompt_agent_name = 'explorer',
                tool_category_keys_json = '["plan_read","chapter_read"]',
                updated_at = CURRENT_TIMESTAMP
            WHERE key = 'clarifier'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE prompt_chain_versions
            SET agent_name = 'explorer'
            WHERE mode_name = 'assistant'
              AND task_name = 'agent'
              AND agent_name = 'clarifier'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE skills
            SET agent_name = 'explorer',
                updated_at = CURRENT_TIMESTAMP
            WHERE agent_name = 'clarifier'
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE skills
            SET agent_name = 'clarifier',
                updated_at = CURRENT_TIMESTAMP
            WHERE agent_name = 'explorer'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE prompt_chain_versions
            SET agent_name = 'clarifier'
            WHERE mode_name = 'assistant'
              AND task_name = 'agent'
              AND agent_name = 'explorer'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE agent_definitions
            SET key = 'clarifier',
                display_name = 'Clarifier',
                prompt_agent_name = 'clarifier',
                tool_category_keys_json = '["artifact","chapter_read"]',
                updated_at = CURRENT_TIMESTAMP
            WHERE key = 'explorer'
            """
        )
    )
