"""add volumes and chapter volume id

Revision ID: 048
Revises: 047
Create Date: 2026-05-29

"""

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.ids import generate_id

revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_VOLUME_TITLE = "第一卷"


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def _create_volumes_table(bind) -> None:
    if "volumes" in _table_names(bind):
        return
    op.create_table(
        "volumes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("chapter_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.UniqueConstraint("project_id", "order", name="uq_volumes_project_order"),
    )
    op.create_index("ix_volumes_project_id", "volumes", ["project_id"])
    op.create_index("ix_volumes_order", "volumes", ["order"])


def _ensure_chapter_volume_column(bind) -> None:
    if "volume_id" not in _column_names(bind, "chapters"):
        op.add_column("chapters", sa.Column("volume_id", sa.String(), nullable=True))
    indexes = _index_names(bind, "chapters")
    if "ix_chapters_volume_id" not in indexes:
        op.create_index("ix_chapters_volume_id", "chapters", ["volume_id"])


def _backfill_default_volumes(bind) -> None:
    now = datetime.utcnow()
    projects = bind.execute(sa.text("SELECT id FROM projects")).fetchall()
    for (project_id,) in projects:
        existing = bind.execute(
            sa.text(
                "SELECT id FROM volumes WHERE project_id = :project_id AND \"order\" = 1"
            ),
            {"project_id": project_id},
        ).fetchone()
        volume_id = existing[0] if existing else generate_id()
        chapter_count = bind.execute(
            sa.text("SELECT COUNT(*) FROM chapters WHERE project_id = :project_id"),
            {"project_id": project_id},
        ).scalar_one()
        if existing is None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO volumes
                    (id, project_id, title, description, "order", chapter_count, created_at, updated_at)
                    VALUES
                    (:id, :project_id, :title, NULL, 1, :chapter_count, :created_at, :updated_at)
                    """
                ),
                {
                    "id": volume_id,
                    "project_id": project_id,
                    "title": DEFAULT_VOLUME_TITLE,
                    "chapter_count": chapter_count,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        else:
            bind.execute(
                sa.text(
                    """
                    UPDATE volumes
                    SET chapter_count = :chapter_count, updated_at = :updated_at
                    WHERE id = :id
                    """
                ),
                {
                    "id": volume_id,
                    "chapter_count": chapter_count,
                    "updated_at": now,
                },
            )
        bind.execute(
            sa.text(
                """
                UPDATE chapters
                SET volume_id = :volume_id
                WHERE project_id = :project_id AND volume_id IS NULL
                """
            ),
            {"volume_id": volume_id, "project_id": project_id},
        )

        chapters = bind.execute(
            sa.text(
                """
                SELECT id
                FROM chapters
                WHERE project_id = :project_id
                ORDER BY "order" ASC, created_at ASC, id ASC
                """
            ),
            {"project_id": project_id},
        ).fetchall()
        for index, (chapter_id,) in enumerate(chapters, start=1):
            bind.execute(
                sa.text(
                    "UPDATE chapters SET \"order\" = :order WHERE id = :chapter_id"
                ),
                {"order": index, "chapter_id": chapter_id},
            )


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)
    if "projects" not in tables or "chapters" not in tables:
        return

    _create_volumes_table(bind)
    _ensure_chapter_volume_column(bind)
    _backfill_default_volumes(bind)

    with op.batch_alter_table("chapters") as batch_op:
        batch_op.alter_column("volume_id", existing_type=sa.String(), nullable=False)
        batch_op.create_foreign_key(
            "fk_chapters_volume_id_volumes",
            "volumes",
            ["volume_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_chapters_volume_order",
            ["volume_id", "order"],
        )


def downgrade() -> None:
    pass
