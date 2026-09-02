"""set safe delete actions for runtime history foreign keys

Revision ID: 1023
Revises: 1022
Create Date: 2026-09-01
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from alembic import op
import sqlalchemy as sa
from sqlalchemy import ForeignKeyConstraint, MetaData, Table
from sqlalchemy.engine import Connection


revision: str = "1023"
down_revision: str | None = "1022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ForeignKeySpec = tuple[str, tuple[str, ...], str, tuple[str, ...], str | None]

_FOREIGN_KEYS: Final[tuple[ForeignKeySpec, ...]] = (
    ("agent_audit_logs", ("task_id",), "tasks", ("id",), "SET NULL"),
    ("agent_audit_logs", ("revision_id",), "revisions", ("id",), "SET NULL"),
    ("agent_audit_logs", ("chapter_id",), "chapters", ("id",), "SET NULL"),
    ("agent_audit_logs", ("project_id",), "projects", ("id",), "CASCADE"),
    ("commits", ("chapter_id",), "chapters", ("id",), "CASCADE"),
    ("commits", ("revision_id",), "revisions", ("id",), "CASCADE"),
)


def _matches_foreign_key(
    constraint: ForeignKeyConstraint,
    local_columns: tuple[str, ...],
    remote_table: str,
    remote_columns: tuple[str, ...],
) -> bool:
    elements = tuple(constraint.elements)
    return (
        tuple(element.parent.name for element in elements) == local_columns
        and tuple(element.target_fullname for element in elements)
        == tuple(f"{remote_table}.{column}" for column in remote_columns)
    )


def _replace_postgresql_foreign_key(
    bind: Connection,
    table_name: str,
    local_columns: tuple[str, ...],
    remote_table: str,
    remote_columns: tuple[str, ...],
    ondelete: str | None,
    constraint_name: str | None,
) -> None:
    foreign_keys = sa.inspect(bind).get_foreign_keys(table_name)
    matching = [
        foreign_key
        for foreign_key in foreign_keys
        if tuple(foreign_key.get("constrained_columns") or ()) == local_columns
        and foreign_key.get("referred_table") == remote_table
        and tuple(foreign_key.get("referred_columns") or ()) == remote_columns
    ]
    expected_action = ondelete.upper() if ondelete else None
    if len(matching) == 1:
        current_action = (matching[0].get("options") or {}).get("ondelete")
        if (
            current_action.upper() if isinstance(current_action, str) else current_action
        ) == expected_action:
            return

    for foreign_key in matching:
        existing_name = foreign_key.get("name")
        if not isinstance(existing_name, str) or not existing_name:
            raise RuntimeError(
                f"无法替换 PostgreSQL 外键: {table_name}.{local_columns} 缺少约束名"
            )
        op.drop_constraint(existing_name, table_name, type_="foreignkey")

    op.create_foreign_key(
        constraint_name,
        table_name,
        remote_table,
        list(local_columns),
        list(remote_columns),
        ondelete=ondelete,
    )


def _replace_sqlite_foreign_keys(
    bind: Connection,
    table_name: str,
    actions: tuple[ForeignKeySpec, ...],
) -> None:
    reflected_metadata = MetaData()
    reflected_table = Table(table_name, reflected_metadata, autoload_with=bind)
    copy_metadata = MetaData()
    copy_table = reflected_table.to_metadata(copy_metadata)
    action_targets = {
        (local_columns, remote_table, remote_columns)
        for _, local_columns, remote_table, remote_columns, _ in actions
    }
    for constraint in list(copy_table.constraints):
        if not isinstance(constraint, ForeignKeyConstraint):
            continue
        if any(
            _matches_foreign_key(
                constraint,
                local_columns,
                remote_table,
                remote_columns,
            )
            for local_columns, remote_table, remote_columns in action_targets
        ):
            copy_table.constraints.remove(constraint)

    for _, local_columns, remote_table, remote_columns, ondelete in actions:
        copy_table.append_constraint(
            ForeignKeyConstraint(
                list(local_columns),
                [f"{remote_table}.{column}" for column in remote_columns],
                ondelete=ondelete,
            )
        )

    with op.batch_alter_table(
        table_name,
        recreate="always",
        copy_from=copy_table,
    ):
        pass


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        tables = {
            table_name: tuple(
                spec for spec in _FOREIGN_KEYS if spec[0] == table_name
            )
            for table_name in {spec[0] for spec in _FOREIGN_KEYS}
        }
        for table_name, actions in tables.items():
            _replace_sqlite_foreign_keys(bind, table_name, actions)
        return

    for table_name, local_columns, remote_table, remote_columns, ondelete in _FOREIGN_KEYS:
        _replace_postgresql_foreign_key(
            bind,
            table_name,
            local_columns,
            remote_table,
            remote_columns,
            ondelete,
            f"fk_{table_name}_{local_columns[0]}_{remote_table}_1023",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        tables = {
            table_name: tuple(
                spec for spec in _FOREIGN_KEYS if spec[0] == table_name
            )
            for table_name in {spec[0] for spec in _FOREIGN_KEYS}
        }
        for table_name, actions in tables.items():
            _replace_sqlite_foreign_keys(
                bind,
                table_name,
                tuple((*spec[:4], None) for spec in actions),
            )
        return

    for table_name, local_columns, remote_table, remote_columns, _ondelete in _FOREIGN_KEYS:
        _replace_postgresql_foreign_key(
            bind,
            table_name,
            local_columns,
            remote_table,
            remote_columns,
            None,
            None,
        )
