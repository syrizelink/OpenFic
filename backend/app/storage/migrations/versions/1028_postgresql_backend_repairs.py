"""Apply PostgreSQL backend repairs and runtime foreign-key fixes.

Revision ID: 1028
Revises: 1027
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from alembic import op
import sqlalchemy as sa
from sqlalchemy import ForeignKeyConstraint, MetaData, Table
from sqlalchemy.engine import Connection


revision: str = "1028"
down_revision: str | Sequence[str] | None = "1027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TASK_CONSTRAINT_NAME = "fk_revisions_task_id_tasks_1028"
_COMMIT_CHAPTER_CONSTRAINT_NAME = "fk_commits_chapter_id_chapters_1028"
_CHARACTER_ORDER_CONSTRAINT_NAME = "ck_character_relationships_order_c"
_CHARACTER_ORDER_CHECK = (
    'source_character_id COLLATE "C" < target_character_id COLLATE "C"'
)
_POSTGRESQL_DEFAULT_FOREIGN_KEY_SUFFIX = "fkey"

ForeignKeySpec = tuple[str, tuple[str, ...], str, tuple[str, ...], str | None]

_FOREIGN_KEYS: Final[tuple[ForeignKeySpec, ...]] = (
    ("agent_audit_logs", ("task_id",), "tasks", ("id",), "SET NULL"),
    ("agent_audit_logs", ("revision_id",), "revisions", ("id",), "SET NULL"),
    ("agent_audit_logs", ("chapter_id",), "chapters", ("id",), "SET NULL"),
    ("agent_audit_logs", ("project_id",), "projects", ("id",), "CASCADE"),
    ("commits", ("chapter_id",), "chapters", ("id",), "CASCADE"),
    ("commits", ("revision_id",), "revisions", ("id",), "CASCADE"),
)


def _foreign_key_columns(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _is_task_foreign_key(foreign_key: Mapping[str, object]) -> bool:
    return (
        _foreign_key_columns(foreign_key.get("constrained_columns")) == ("task_id",)
        and foreign_key.get("referred_table") == "tasks"
        and _foreign_key_columns(foreign_key.get("referred_columns")) == ("id",)
    )


def _is_offline() -> bool:
    return op.get_context().as_sql


def _has_task_foreign_key(bind: Connection) -> bool:
    if _is_offline():
        return False
    return any(
        _is_task_foreign_key(foreign_key)
        for foreign_key in sa.inspect(bind).get_foreign_keys("revisions")
    )


def _has_repair_foreign_key(bind: Connection) -> bool:
    if _is_offline():
        return True
    return any(
        foreign_key.get("name") == _TASK_CONSTRAINT_NAME
        and _is_task_foreign_key(foreign_key)
        for foreign_key in sa.inspect(bind).get_foreign_keys("revisions")
    )


def _repair_revisions_task_foreign_key(bind: Connection) -> None:
    if _has_task_foreign_key(bind):
        return
    if _is_offline() and bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE revisions "
                "DROP CONSTRAINT IF EXISTS revisions_task_id_fkey"
            )
        )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("revisions", recreate="always") as batch_op:
            batch_op.create_foreign_key(
                _TASK_CONSTRAINT_NAME,
                "tasks",
                ["task_id"],
                ["id"],
            )
        return
    op.create_foreign_key(
        _TASK_CONSTRAINT_NAME,
        "revisions",
        "tasks",
        ["task_id"],
        ["id"],
    )


def _restore_revisions_task_foreign_key(bind: Connection) -> None:
    if not _has_repair_foreign_key(bind):
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("revisions", recreate="always") as batch_op:
            batch_op.drop_constraint(_TASK_CONSTRAINT_NAME, type_="foreignkey")
        return
    op.drop_constraint(_TASK_CONSTRAINT_NAME, "revisions", type_="foreignkey")


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


def _postgresql_default_foreign_key_name(
    table_name: str, local_columns: tuple[str, ...]
) -> str:
    return (
        f"{table_name}_{'_'.join(local_columns)}_"
        f"{_POSTGRESQL_DEFAULT_FOREIGN_KEY_SUFFIX}"
    )


def _replace_postgresql_foreign_key(
    bind: Connection,
    table_name: str,
    local_columns: tuple[str, ...],
    remote_table: str,
    remote_columns: tuple[str, ...],
    ondelete: str | None,
    constraint_name: str | None,
    existing_constraint_name: str | None = None,
) -> None:
    if _is_offline():
        existing_name = existing_constraint_name or (
            constraint_name
            if ondelete is None and constraint_name
            else _postgresql_default_foreign_key_name(table_name, local_columns)
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
        return

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


def _set_runtime_foreign_key_actions(bind: Connection, *, restore: bool = False) -> None:
    if bind.dialect.name == "sqlite":
        tables = {
            table_name: tuple(
                (
                    spec[0],
                    spec[1],
                    spec[2],
                    spec[3],
                    None if restore else spec[4],
                )
                for spec in _FOREIGN_KEYS
                if spec[0] == table_name
            )
            for table_name in {spec[0] for spec in _FOREIGN_KEYS}
        }
        for table_name, actions in tables.items():
            _replace_sqlite_foreign_keys(bind, table_name, actions)
        return

    for table_name, local_columns, remote_table, remote_columns, ondelete in _FOREIGN_KEYS:
        action = None if restore else ondelete
        constraint_name = f"fk_{table_name}_{local_columns[0]}_{remote_table}_1028"
        existing_constraint_name = (
            _COMMIT_CHAPTER_CONSTRAINT_NAME
            if restore
            and table_name == "commits"
            and local_columns == ("chapter_id",)
            else constraint_name if restore else None
        )
        _replace_postgresql_foreign_key(
            bind,
            table_name,
            local_columns,
            remote_table,
            remote_columns,
            action,
            None if restore else constraint_name,
            existing_constraint_name,
        )


def _matching_commit_chapter_foreign_keys(bind: Connection) -> list[Mapping[str, object]]:
    if _is_offline():
        return []
    return [
        foreign_key
        for foreign_key in sa.inspect(bind).get_foreign_keys("commits")
        if tuple(foreign_key.get("constrained_columns") or ()) == ("chapter_id",)
        and foreign_key.get("referred_table") == "chapters"
        and tuple(foreign_key.get("referred_columns") or ()) == ("id",)
    ]


def _copy_commits(bind: Connection, include_chapter_foreign_key: bool) -> Table:
    reflected_metadata = MetaData()
    reflected_table = Table("commits", reflected_metadata, autoload_with=bind)
    copy_metadata = MetaData()
    copy_table = reflected_table.to_metadata(copy_metadata)
    if not include_chapter_foreign_key:
        for constraint in list(copy_table.constraints):
            if isinstance(constraint, ForeignKeyConstraint) and _matches_foreign_key(
                constraint, ("chapter_id",), "chapters", ("id",)
            ):
                copy_table.constraints.remove(constraint)
    elif not any(
        isinstance(constraint, ForeignKeyConstraint)
        and _matches_foreign_key(constraint, ("chapter_id",), "chapters", ("id",))
        for constraint in copy_table.constraints
    ):
        copy_table.append_constraint(
            ForeignKeyConstraint(
                ["chapter_id"],
                ["chapters.id"],
                name=_COMMIT_CHAPTER_CONSTRAINT_NAME,
                ondelete="CASCADE",
            )
        )
    return copy_table


def _remove_commit_chapter_foreign_key(bind: Connection) -> None:
    if _is_offline():
        op.drop_constraint(
            _COMMIT_CHAPTER_CONSTRAINT_NAME,
            "commits",
            type_="foreignkey",
        )
        return

    matching = _matching_commit_chapter_foreign_keys(bind)
    if not matching:
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "commits",
            recreate="always",
            copy_from=_copy_commits(bind, include_chapter_foreign_key=False),
        ):
            pass
        return
    for foreign_key in matching:
        name = foreign_key.get("name")
        if not isinstance(name, str) or not name:
            raise RuntimeError("无法删除 commits.chapter_id 外键: 缺少约束名")
        op.drop_constraint(name, "commits", type_="foreignkey")


def _restore_commit_chapter_foreign_key(bind: Connection) -> None:
    if _is_offline():
        op.create_foreign_key(
            _COMMIT_CHAPTER_CONSTRAINT_NAME,
            "commits",
            "chapters",
            ["chapter_id"],
            ["id"],
            ondelete="CASCADE",
        )
        return

    if _matching_commit_chapter_foreign_keys(bind):
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "commits",
            recreate="always",
            copy_from=_copy_commits(bind, include_chapter_foreign_key=True),
        ):
            pass
        return
    op.create_foreign_key(
        None,
        "commits",
        "chapters",
        ["chapter_id"],
        ["id"],
        ondelete="CASCADE",
    )


def _matching_character_order_checks(bind: Connection) -> list[Mapping[str, object]]:
    if _is_offline():
        return []
    return [
        constraint
        for constraint in sa.inspect(bind).get_check_constraints("character_relationships")
        if "source_character_id" in str(constraint.get("sqltext", ""))
        and "target_character_id" in str(constraint.get("sqltext", ""))
    ]


def _repair_character_relationship_order(bind: Connection) -> None:
    if bind.dialect.name != "postgresql":
        return
    if _is_offline():
        op.execute(
            sa.text(
                """
                DO $$
                DECLARE constraint_name text;
                BEGIN
                    SELECT conname INTO constraint_name
                    FROM pg_constraint
                    WHERE conrelid = 'character_relationships'::regclass
                      AND contype = 'c'
                      AND pg_get_constraintdef(oid) LIKE '%source_character_id%'
                      AND pg_get_constraintdef(oid) LIKE '%target_character_id%'
                    LIMIT 1;
                    IF constraint_name IS NOT NULL THEN
                        EXECUTE format(
                            'ALTER TABLE character_relationships DROP CONSTRAINT %I',
                            constraint_name
                        );
                    END IF;
                END $$
                """
            )
        )
    else:
        for constraint in _matching_character_order_checks(bind):
            name = constraint.get("name")
            if isinstance(name, str) and name:
                op.drop_constraint(name, "character_relationships", type_="check")
    for table_name in ("character_relationships", "revision_character_relationship_snapshots"):
        op.execute(sa.text(
            f'UPDATE {table_name} SET source_character_id = target_character_id, '
            'target_character_id = source_character_id '
            'WHERE source_character_id COLLATE "C" > target_character_id COLLATE "C"'
        ))
    op.create_check_constraint(
        _CHARACTER_ORDER_CONSTRAINT_NAME,
        "character_relationships",
        _CHARACTER_ORDER_CHECK,
    )


def _restore_character_relationship_order(bind: Connection) -> None:
    if bind.dialect.name != "postgresql":
        return
    if _is_offline():
        op.drop_constraint(
            _CHARACTER_ORDER_CONSTRAINT_NAME,
            "character_relationships",
            type_="check",
        )
    else:
        for constraint in _matching_character_order_checks(bind):
            name = constraint.get("name")
            if isinstance(name, str) and name:
                op.drop_constraint(name, "character_relationships", type_="check")
    for table_name in ("character_relationships", "revision_character_relationship_snapshots"):
        op.execute(sa.text(
            f"UPDATE {table_name} SET source_character_id = target_character_id, "
            "target_character_id = source_character_id "
            "WHERE source_character_id > target_character_id"
        ))
    op.create_check_constraint(
        None,
        "character_relationships",
        "source_character_id < target_character_id",
    )


def upgrade() -> None:
    bind = op.get_bind()
    _repair_revisions_task_foreign_key(bind)
    _set_runtime_foreign_key_actions(bind)
    _remove_commit_chapter_foreign_key(bind)
    _repair_character_relationship_order(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _restore_character_relationship_order(bind)
    _restore_commit_chapter_foreign_key(bind)
    _set_runtime_foreign_key_actions(bind, restore=True)
    _restore_revisions_task_foreign_key(bind)
