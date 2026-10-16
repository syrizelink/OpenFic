"""Expand the attachment MIME type column.

Revision ID: 1029
Revises: 1028
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision: str = "1029"
down_revision: str = "1028"
branch_labels: str | None = None
depends_on: str | None = None


_LEGACY_MIME_TYPE_LENGTH = 50
_MIME_TYPE_LENGTH = 255


def _is_offline() -> bool:
    return op.get_context().as_sql


def _alter_mime_type(*, existing_length: int, target_length: int) -> None:
    if op.get_context().dialect.name == "sqlite":
        with op.batch_alter_table(
            "agent_attachments",
            recreate="always",
        ) as batch_op:
            batch_op.alter_column(
                "mime_type",
                existing_type=sa.String(length=existing_length),
                type_=sa.String(length=target_length),
                existing_nullable=False,
            )
        return

    op.alter_column(
        "agent_attachments",
        "mime_type",
        existing_type=sa.String(length=existing_length),
        type_=sa.String(length=target_length),
        existing_nullable=False,
    )


def _has_overlong_mime_type(connection: Connection) -> bool:
    return (
        connection.execute(
            sa.text(
                "SELECT 1 FROM agent_attachments "
                "WHERE length(mime_type) > :max_length LIMIT 1"
            ),
            {"max_length": _LEGACY_MIME_TYPE_LENGTH},
        ).first()
        is not None
    )


def upgrade() -> None:
    _alter_mime_type(
        existing_length=_LEGACY_MIME_TYPE_LENGTH,
        target_length=_MIME_TYPE_LENGTH,
    )


def downgrade() -> None:
    if not _is_offline() and _has_overlong_mime_type(op.get_bind()):
        raise RuntimeError(
            "无法将 agent_attachments.mime_type 降级为 VARCHAR(50)："
            "存在超过 50 个字符的 MIME 值，拒绝截断"
        )

    _alter_mime_type(
        existing_length=_MIME_TYPE_LENGTH,
        target_length=_LEGACY_MIME_TYPE_LENGTH,
    )
