"""keep commit chapter references after chapter deletion

Revision ID: 1024
Revises: 1023
Create Date: 2026-09-02
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import ForeignKeyConstraint, MetaData, Table
from sqlalchemy.engine import Connection


revision: str = "1024"
down_revision: str | None = "1023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "fk_commits_chapter_id_chapters_1023"


def _matches_chapter_foreign_key(
    constraint: ForeignKeyConstraint,
) -> bool:
    elements = tuple(constraint.elements)
    return (
        tuple(element.parent.name for element in elements) == ("chapter_id",)
        and tuple(element.target_fullname for element in elements) == ("chapters.id",)
    )


def _matching_foreign_keys(bind: Connection) -> list[Mapping[str, object]]:
    return [
        foreign_key
        for foreign_key in sa.inspect(bind).get_foreign_keys("commits")
        if tuple(foreign_key.get("constrained_columns") or ()) == ("chapter_id",)
        and foreign_key.get("referred_table") == "chapters"
        and tuple(foreign_key.get("referred_columns") or ()) == ("id",)
    ]


def _copy_commits_without_chapter_foreign_key(bind: Connection) -> Table:
    reflected_metadata = MetaData()
    reflected_table = Table("commits", reflected_metadata, autoload_with=bind)
    copy_metadata = MetaData()
    copy_table = reflected_table.to_metadata(copy_metadata)
    for constraint in list(copy_table.constraints):
        if isinstance(constraint, ForeignKeyConstraint) and _matches_chapter_foreign_key(
            constraint
        ):
            copy_table.constraints.remove(constraint)
    return copy_table


def _copy_commits_with_chapter_foreign_key(bind: Connection) -> Table:
    reflected_metadata = MetaData()
    reflected_table = Table("commits", reflected_metadata, autoload_with=bind)
    copy_metadata = MetaData()
    copy_table = reflected_table.to_metadata(copy_metadata)
    if not any(
        isinstance(constraint, ForeignKeyConstraint)
        and _matches_chapter_foreign_key(constraint)
        for constraint in copy_table.constraints
    ):
        copy_table.append_constraint(
            ForeignKeyConstraint(
                ["chapter_id"],
                ["chapters.id"],
                name=CONSTRAINT_NAME,
                ondelete="CASCADE",
            )
        )
    return copy_table


def upgrade() -> None:
    bind = op.get_bind()
    if not _matching_foreign_keys(bind):
        return

    if bind.dialect.name == "sqlite":
        copy_table = _copy_commits_without_chapter_foreign_key(bind)
        with op.batch_alter_table(
            "commits",
            recreate="always",
            copy_from=copy_table,
        ):
            pass
        return

    for foreign_key in _matching_foreign_keys(bind):
        name = foreign_key.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError("无法删除 commits.chapter_id 外键: 缺少约束名")
        op.drop_constraint(name, "commits", type_="foreignkey")


def downgrade() -> None:
    bind = op.get_bind()
    if _matching_foreign_keys(bind):
        return

    if bind.dialect.name == "sqlite":
        copy_table = _copy_commits_with_chapter_foreign_key(bind)
        with op.batch_alter_table(
            "commits",
            recreate="always",
            copy_from=copy_table,
        ):
            pass
        return

    op.create_foreign_key(
        CONSTRAINT_NAME,
        "commits",
        "chapters",
        ["chapter_id"],
        ["id"],
        ondelete="CASCADE",
    )
