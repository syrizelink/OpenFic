"""add portable project pinyin columns

Revision ID: 1023
Revises: 1022
Create Date: 2026-08-26 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from app.core.pinyin import to_pinyin, to_pinyin_initials


revision: str = "1023"
down_revision: str | Sequence[str] | None = "1022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column_name in (
        "title_pinyin_full",
        "title_pinyin_initials",
        "description_pinyin_full",
        "description_pinyin_initials",
    ):
        op.add_column(
            "projects",
            sa.Column(column_name, sa.String(), nullable=False, server_default=""),
        )

    bind = op.get_bind()
    projects = bind.execute(
        sa.text("SELECT id, title, description FROM projects")
    ).mappings()
    update = sa.text(
        """
        UPDATE projects
        SET title_pinyin_full = :title_full,
            title_pinyin_initials = :title_initials,
            description_pinyin_full = :description_full,
            description_pinyin_initials = :description_initials
        WHERE id = :project_id
        """
    )
    for project in projects:
        bind.execute(
            update,
            {
                "project_id": project["id"],
                "title_full": to_pinyin(project["title"]),
                "title_initials": to_pinyin_initials(project["title"]),
                "description_full": to_pinyin(project["description"]),
                "description_initials": to_pinyin_initials(project["description"]),
            },
        )

    op.create_index(
        "ix_projects_title_pinyin_full",
        "projects",
        ["title_pinyin_full"],
        unique=False,
    )
    op.create_index(
        "ix_projects_title_pinyin_initials",
        "projects",
        ["title_pinyin_initials"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_projects_title_pinyin_initials", table_name="projects")
    op.drop_index("ix_projects_title_pinyin_full", table_name="projects")
    for column_name in (
        "description_pinyin_initials",
        "description_pinyin_full",
        "title_pinyin_initials",
        "title_pinyin_full",
    ):
        op.drop_column("projects", column_name)
