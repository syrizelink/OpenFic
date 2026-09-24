"""One-shot, validated migration from an OpenFic SQLite database to PostgreSQL."""

from __future__ import annotations

import base64
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table, create_engine, func, inspect, select, text
from sqlalchemy.engine import Connection, Engine

from app.storage.database import ALEMBIC_INI_PATH
from app.storage.urls import normalize_postgres_url


_INTERNAL_TABLES = {"alembic_version", "openfic_maintenance_migrations"}
_DEFAULT_BATCH_SIZE = 1_000


@dataclass(frozen=True)
class TableMigrationResult:
    table_name: str
    row_count: int
    checksum: str


@dataclass(frozen=True)
class MigrationReport:
    tables: tuple[TableMigrationResult, ...]
    deferred_foreign_keys: int

    @property
    def total_rows(self) -> int:
        return sum(table.row_count for table in self.tables)


def check_sqlite_source(source_path: Path) -> None:
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite source does not exist: {source_path}")
    with sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            preview = foreign_key_errors[:10]
            raise RuntimeError(
                f"SQLite contains {len(foreign_key_errors)} foreign-key violations: {preview}"
            )
        version_rows = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall()
        expected_head = ScriptDirectory.from_config(
            Config(str(ALEMBIC_INI_PATH))
        ).get_current_head()
        if version_rows != [(expected_head,)]:
            current_version = version_rows or "missing"
            raise RuntimeError(
                f"SQLite schema must be upgraded to {expected_head}; "
                f"current version is {current_version}"
            )


def prepare_postgres_schema(database_url: str) -> None:
    config = Config(str(ALEMBIC_INI_PATH))
    config.attributes["database_url"] = normalize_postgres_url(database_url)
    command.upgrade(config, "head")


def _reflect_tables(engine: Engine) -> dict[str, Table]:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    return {
        name: table
        for name, table in metadata.tables.items()
        if name not in _INTERNAL_TABLES and not name.startswith("sqlite_")
    }


def _copy_order(tables: Mapping[str, Table]) -> list[str]:
    pending = set(tables)
    copied: set[str] = set()
    ordered: list[str] = []
    while pending:
        ready = sorted(
            table_name
            for table_name in pending
            if all(
                foreign_key.column.table.name in copied
                or foreign_key.column.table.name not in tables
                or foreign_key.parent.nullable
                for foreign_key in tables[table_name].foreign_keys
            )
        )
        if not ready:
            blocked = ", ".join(sorted(pending))
            raise RuntimeError(
                "Non-nullable foreign-key cycle prevents migration: " + blocked
            )
        for table_name in ready:
            pending.remove(table_name)
            copied.add(table_name)
            ordered.append(table_name)
    return ordered


def _normalized_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"bytes": base64.b64encode(value).decode("ascii")}
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _normalized_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalized_value(item) for item in value]
    return value


def _rows_checksum(rows: Iterable[Mapping[str, Any]], primary_keys: list[str]) -> str:
    normalized_rows = [
        {key: _normalized_value(value) for key, value in sorted(row.items())}
        for row in rows
    ]
    normalized_rows.sort(
        key=lambda row: tuple(str(row.get(primary_key)) for primary_key in primary_keys)
    )
    payload = json.dumps(
        normalized_rows,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _table_rows(connection: Connection, table: Table) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(select(table)).mappings()]


def _ensure_target_is_empty(connection: Connection, tables: Mapping[str, Table]) -> None:
    nonempty = []
    for table_name, table in sorted(tables.items()):
        row_count = connection.scalar(select(func.count()).select_from(table))
        if row_count:
            nonempty.append(f"{table_name}={row_count}")
    if nonempty:
        raise RuntimeError(
            "Target business tables must be empty before migration: " + ", ".join(nonempty)
        )


def _check_target(engine: Engine, source_tables: Mapping[str, Table]) -> None:
    """Reject existing data or incompatible schemas before any DDL is executed."""
    names = set(inspect(engine).get_table_names())
    if not names:
        return
    target_tables = _reflect_tables(engine)
    with engine.connect() as connection:
        _ensure_target_is_empty(connection, target_tables)
        expected_head = ScriptDirectory.from_config(Config(str(ALEMBIC_INI_PATH))).get_current_head()
        if "alembic_version" not in names or connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalars().all() != [expected_head]:
            raise RuntimeError("Target must be empty or have the current Alembic schema")
    if set(target_tables) != set(source_tables):
        raise RuntimeError("Source and target table sets differ; use a fresh target database")
    for name, table in source_tables.items():
        if set(table.c.keys()) != set(target_tables[name].c.keys()):
            raise RuntimeError(f"Source and target columns differ for {name}")


def migrate_sqlite_to_postgres(
    source_path: Path,
    database_url: str,
    *,
    apply: bool = False,
    batch_size: int = _DEFAULT_BATCH_SIZE,
) -> MigrationReport:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    source_path = source_path.resolve()
    check_sqlite_source(source_path)
    target_url = normalize_postgres_url(database_url)
    source_engine = create_engine(
        "sqlite://",
        creator=lambda: sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True),
    )
    target_engine = create_engine(
        target_url, pool_pre_ping=True, connect_args={"options": "-c timezone=UTC"},
    )
    try:
        source_tables = _reflect_tables(source_engine)
        _check_target(target_engine, source_tables)
        if apply:
            prepare_postgres_schema(target_url)
            _check_target(target_engine, source_tables)
        target_tables = _reflect_tables(target_engine)
        source_order = _copy_order(source_tables)
        results: list[TableMigrationResult] = []

        with source_engine.connect() as source_connection:
            source_connection.exec_driver_sql("BEGIN")
            if not apply:
                existing_target_tables = {
                    name: target_tables[name]
                    for name in source_tables
                    if name in target_tables
                }
                with target_engine.connect() as target_connection:
                    _ensure_target_is_empty(
                        target_connection,
                        existing_target_tables,
                    )
                for table_name in source_order:
                    source_table = source_tables[table_name]
                    rows = _table_rows(source_connection, source_table)
                    primary_keys = [column.name for column in source_table.primary_key]
                    results.append(
                        TableMigrationResult(
                            table_name,
                            len(rows),
                            _rows_checksum(rows, primary_keys),
                        )
                    )
                return MigrationReport(tuple(results), 0)

        missing_tables = sorted(set(source_tables) - set(target_tables))
        if missing_tables:
            raise RuntimeError(
                "Target schema is missing source tables: " + ", ".join(missing_tables)
            )
        migration_tables = {
            name: target_tables[name]
            for name in source_tables
            if name in target_tables
        }
        order = _copy_order(migration_tables)
        deferred_updates: list[tuple[Table, dict[str, Any], dict[str, Any]]] = []

        with source_engine.connect() as source_connection:
            source_connection.exec_driver_sql("BEGIN")
            with target_engine.begin() as target_connection:
                _ensure_target_is_empty(target_connection, migration_tables)
                copied: set[str] = set()
                for table_name in order:
                    source_table = source_tables[table_name]
                    target_table = target_tables[table_name]
                    rows = _table_rows(source_connection, source_table)
                    primary_keys = [column.name for column in source_table.primary_key]
                    for row in rows:
                        deferred_values: dict[str, Any] = {}
                        for foreign_key in target_table.foreign_keys:
                            parent_table = foreign_key.column.table.name
                            column_name = foreign_key.parent.name
                            if (
                                parent_table not in copied
                                and row.get(column_name) is not None
                            ):
                                if not foreign_key.parent.nullable:
                                    raise RuntimeError(
                                        f"Cannot defer non-nullable foreign key "
                                        f"{table_name}.{column_name}"
                                    )
                                deferred_values[column_name] = row[column_name]
                                row[column_name] = None
                        if deferred_values:
                            identity = {
                                primary_key: row[primary_key]
                                for primary_key in primary_keys
                            }
                            deferred_updates.append(
                                (target_table, identity, deferred_values)
                            )
                    for start in range(0, len(rows), batch_size):
                        target_connection.execute(
                            target_table.insert(),
                            rows[start : start + batch_size],
                        )
                    copied.add(table_name)
                    results.append(
                        TableMigrationResult(
                            table_name,
                            len(rows),
                            _rows_checksum(
                                _table_rows(source_connection, source_table),
                                primary_keys,
                            ),
                        )
                    )

                for table, identity, deferred_values in deferred_updates:
                    where_clause = None
                    for column_name, value in identity.items():
                        predicate = table.c[column_name] == value
                        where_clause = (
                            predicate
                            if where_clause is None
                            else where_clause & predicate
                        )
                    if where_clause is None:
                        raise RuntimeError(f"Table {table.name} has no primary key")
                    target_connection.execute(
                        table.update().where(where_clause).values(**deferred_values)
                    )

                _verify_copy(
                    source_connection,
                    target_connection,
                    source_tables,
                    target_tables,
                    order,
                )
        return MigrationReport(tuple(results), len(deferred_updates))
    finally:
        source_engine.dispose()
        target_engine.dispose()


def _verify_copy(
    source_connection: Connection,
    target_connection: Connection,
    source_tables: Mapping[str, Table],
    target_tables: Mapping[str, Table],
    table_names: Iterable[str],
) -> None:
    errors: list[str] = []
    for table_name in table_names:
        source_table = source_tables[table_name]
        target_table = target_tables[table_name]
        primary_keys = [column.name for column in source_table.primary_key]
        source_rows = _table_rows(source_connection, source_table)
        target_rows = _table_rows(target_connection, target_table)
        if len(source_rows) != len(target_rows):
            errors.append(
                f"{table_name}: source={len(source_rows)}, target={len(target_rows)}"
            )
            continue
        source_checksum = _rows_checksum(source_rows, primary_keys)
        target_checksum = _rows_checksum(target_rows, primary_keys)
        if source_checksum != target_checksum:
            errors.append(f"{table_name}: checksum mismatch")
    if errors:
        raise RuntimeError("Post-migration verification failed: " + "; ".join(errors))
