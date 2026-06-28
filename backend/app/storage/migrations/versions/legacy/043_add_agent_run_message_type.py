"""add agent run message type fields

Revision ID: 043
Revises: 042
Create Date: 2026-05-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "agent_run_messages")
    indexes = _index_names(bind, "agent_run_messages")

    with op.batch_alter_table("agent_run_messages") as batch_op:
        if "message_type" not in columns:
            batch_op.add_column(
                sa.Column(
                    "message_type",
                    sa.String(length=50),
                    nullable=False,
                    server_default="message",
                )
            )
        if "display_channel" not in columns:
            batch_op.add_column(
                sa.Column(
                    "display_channel",
                    sa.String(length=20),
                    nullable=False,
                    server_default="list",
                )
            )
        if "ix_agent_run_messages_message_type" not in indexes:
            batch_op.create_index("ix_agent_run_messages_message_type", ["message_type"])
        if "ix_agent_run_messages_display_channel" not in indexes:
            batch_op.create_index(
                "ix_agent_run_messages_display_channel", ["display_channel"]
            )


def downgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "agent_run_messages")
    indexes = _index_names(bind, "agent_run_messages")

    with op.batch_alter_table("agent_run_messages") as batch_op:
        if "ix_agent_run_messages_display_channel" in indexes:
            batch_op.drop_index("ix_agent_run_messages_display_channel")
        if "ix_agent_run_messages_message_type" in indexes:
            batch_op.drop_index("ix_agent_run_messages_message_type")
        if "display_channel" in columns:
            batch_op.drop_column("display_channel")
        if "message_type" in columns:
            batch_op.drop_column("message_type")
