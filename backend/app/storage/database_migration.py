"""同步迁移主业务数据库。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Integer,
    JSON,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Table,
    and_,
    bindparam,
    create_engine,
    func,
    or_,
    select,
)
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.sql.schema import Column, ForeignKeyConstraint

from app.settings import settings, to_sync_database_url


ALEMBIC_DATABASE_URL_ATTRIBUTE = "openfic_database_url"
_ALEMBIC_CONNECTION_ATTRIBUTE = "openfic_connection"
_ALEMBIC_VERSION_TABLE = "alembic_version"
_BATCH_SIZE = 500
_ALEMBIC_INI_PATH = Path(__file__).resolve().parents[2] / "alembic.ini"
_NON_BUSINESS_TABLES = {
    _ALEMBIC_VERSION_TABLE,
    "openfic_maintenance_migrations",
}


class DatabaseMigrationError(RuntimeError):
    """数据库迁移预检、导入或校验失败。"""


@dataclass(frozen=True)
class MigrationReport:
    """主业务库迁移结果。"""

    source_dialect: str
    target_dialect: str
    table_count: int
    row_count: int
    checksum: str
    repaired_foreign_key_values: int = 0
    deleted_orphaned_rows: int = 0

    def summary(self) -> str:
        return (
            "数据库迁移完成 "
            f"source={self.source_dialect} target={self.target_dialect} "
            f"tables={self.table_count} rows={self.row_count} "
            "checks=rows,primary-keys,foreign-keys,checksum:ok "
            f"repairs={self.repaired_foreign_key_values} "
            f"deletions={self.deleted_orphaned_rows}"
        )


@dataclass(frozen=True)
class _DatabaseStats:
    row_counts: dict[str, int]
    checksum: str


_ForeignKeyRepairs = dict[str, dict[tuple[object, ...], set[str]]]
_ForeignKeyDeletions = dict[str, set[tuple[object, ...]]]


def resolve_source_url(source_url: str | None) -> str:
    """解析迁移源 URL，未指定时使用当前主业务库配置。"""
    return source_url or settings.database_sync_url


def _create_alembic_config(
    database_url: str,
    connection: Connection | None = None,
) -> Config:
    config = Config(str(_ALEMBIC_INI_PATH))
    config.attributes[ALEMBIC_DATABASE_URL_ATTRIBUTE] = database_url
    if connection is not None:
        config.attributes[_ALEMBIC_CONNECTION_ATTRIBUTE] = connection
    return config


def _prepare_database_url(database_url: str, label: str) -> tuple[str, str]:
    if not database_url or not database_url.strip():
        raise DatabaseMigrationError(f"{label}数据库 URL 不能为空")

    try:
        sync_url = to_sync_database_url(database_url.strip())
        parsed_url = make_url(sync_url)
    except Exception as exc:
        raise DatabaseMigrationError(f"{label}数据库 URL 无效") from exc

    dialect = parsed_url.get_backend_name()
    if dialect not in {"sqlite", "postgresql"}:
        raise DatabaseMigrationError(
            f"{label}数据库方言不受支持: 仅支持 SQLite 或 PostgreSQL"
        )
    if dialect == "postgresql" and parsed_url.get_driver_name() != "psycopg":
        raise DatabaseMigrationError(f"{label}数据库必须使用同步 psycopg 驱动")
    return sync_url, dialect


def _create_database_engine(database_url: str, label: str) -> tuple[Engine, str]:
    sync_url, dialect = _prepare_database_url(database_url, label)
    try:
        return create_engine(sync_url), dialect
    except Exception as exc:
        raise _wrap_error(f"无法创建{label}数据库引擎", exc, (database_url,)) from exc


def _wrap_error(
    message: str, exc: Exception, database_urls: tuple[str, ...]
) -> DatabaseMigrationError:
    detail = str(exc).strip()
    parsed_urls = []
    for database_url in database_urls:
        candidate_urls = [database_url]
        try:
            candidate_urls.append(to_sync_database_url(database_url))
        except Exception:
            pass
        for candidate_url in candidate_urls:
            try:
                parsed_url = make_url(candidate_url)
            except Exception:
                continue
            parsed_urls.append(parsed_url)
            raw_url = parsed_url.render_as_string(hide_password=False)
            safe_url = parsed_url.render_as_string(hide_password=True)
            detail = detail.replace(raw_url, "<database-url>")
            detail = detail.replace(safe_url, "<database-url>")
    for parsed_url in parsed_urls:
        if parsed_url.password:
            detail = detail.replace(parsed_url.password, "<redacted>")
    if not detail:
        detail = type(exc).__name__
    return DatabaseMigrationError(f"{message}: {detail}")


def _business_table_names(metadata: MetaData) -> tuple[str, ...]:
    return tuple(
        sorted(name for name in metadata.tables if name not in _NON_BUSINESS_TABLES)
    )


def _reflect_metadata(
    connection: Connection,
    label: str,
    database_url: str | None = None,
) -> MetaData:
    metadata = MetaData()
    try:
        metadata.reflect(bind=connection)
    except Exception as exc:
        database_urls = (database_url,) if database_url else ()
        raise _wrap_error(f"无法读取{label}数据库 schema", exc, database_urls) from exc
    return metadata


def _validate_source_revision(connection: Connection, database_url: str) -> None:
    config = _create_alembic_config(database_url)
    try:
        expected_heads = set(ScriptDirectory.from_config(config).get_heads())
        actual_heads = set(MigrationContext.configure(connection).get_current_heads())
    except Exception as exc:
        raise _wrap_error(
            "无法读取源数据库 Alembic revision", exc, (database_url,)
        ) from exc

    if actual_heads != expected_heads:
        actual = ", ".join(sorted(actual_heads)) or "未设置"
        expected = ", ".join(sorted(expected_heads)) or "未找到"
        raise DatabaseMigrationError(
            f"源数据库 Alembic revision 不匹配: 当前={actual}，要求={expected}；"
            "拒绝迁移 legacy 或未完成迁移的数据库"
        )


def _foreign_key_signature(
    constraint: ForeignKeyConstraint,
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            (
                element.parent.name,
                element.column.table.name,
                element.column.name,
            )
            for element in constraint.elements
        )
    )


def _validate_foreign_key_definitions(
    metadata: MetaData,
    table_names: tuple[str, ...],
    label: str,
) -> None:
    allowed_tables = set(table_names)
    for table_name in table_names:
        table = metadata.tables[table_name]
        for constraint in table.foreign_key_constraints:
            for element in constraint.elements:
                local_column = element.parent.name
                remote_table = element.column.table.name
                if local_column not in table.c:
                    raise DatabaseMigrationError(
                        f"{label}表 {table_name} 的外键列不存在: {local_column}"
                    )
                if remote_table not in allowed_tables:
                    raise DatabaseMigrationError(
                        f"{label}表 {table_name} 的外键目标表不存在: {remote_table}"
                    )


def _validate_schema(
    source_metadata: MetaData,
    target_metadata: MetaData,
    table_names: tuple[str, ...],
) -> None:
    source_tables = set(_business_table_names(source_metadata))
    target_tables = set(_business_table_names(target_metadata))
    expected_tables = set(table_names)
    if source_tables != expected_tables or target_tables != expected_tables:
        missing = sorted(expected_tables - target_tables)
        extra = sorted(target_tables - expected_tables)
        raise DatabaseMigrationError(
            "源/目标业务表集合不匹配"
            f"（目标缺少={missing or '无'}，目标多出={extra or '无'}）"
        )

    for table_name in table_names:
        source_table = source_metadata.tables[table_name]
        target_table = target_metadata.tables[table_name]
        source_columns = set(source_table.c.keys())
        target_columns = set(target_table.c.keys())
        if source_columns != target_columns:
            raise DatabaseMigrationError(
                f"表 {table_name} 的列结构不匹配，拒绝猜测转换"
            )
        for column_name in source_columns:
            source_column = source_table.c[column_name]
            target_column = target_table.c[column_name]
            if _column_signature(source_column) != _column_signature(target_column):
                raise DatabaseMigrationError(
                    f"表 {table_name} 的列结构不匹配，拒绝猜测转换"
                )

        source_primary_key = tuple(
            column.name for column in source_table.primary_key.columns
        )
        target_primary_key = tuple(
            column.name for column in target_table.primary_key.columns
        )
        if source_primary_key != target_primary_key:
            raise DatabaseMigrationError(f"表 {table_name} 的主键结构不匹配")

        source_foreign_keys = {
            _foreign_key_signature(constraint)
            for constraint in source_table.foreign_key_constraints
        }
        target_foreign_keys = {
            _foreign_key_signature(constraint)
            for constraint in target_table.foreign_key_constraints
        }
        if source_foreign_keys != target_foreign_keys:
            raise DatabaseMigrationError(f"表 {table_name} 的外键结构不匹配")


def _column_signature(column: Column[Any]) -> tuple[object, ...]:
    column_type = column.type
    if isinstance(column_type, Boolean):
        type_signature: tuple[object, ...] = ("boolean",)
    elif isinstance(column_type, (Integer, BigInteger)):
        type_signature = ("integer",)
    elif isinstance(column_type, Float):
        type_signature = ("float",)
    elif isinstance(column_type, Numeric):
        type_signature = ("number", column_type.precision, column_type.scale)
    elif isinstance(column_type, DateTime):
        type_signature = ("datetime",)
    elif isinstance(column_type, LargeBinary):
        type_signature = ("bytes", column_type.length)
    elif isinstance(column_type, JSON):
        type_signature = (column_type.__class__.__name__.lower(),)
    elif isinstance(column_type, String):
        type_signature = ("string", column_type.length)
    else:
        type_signature = (
            column_type.__class__.__module__,
            column_type.__class__.__name__,
        )
    return (*type_signature, bool(column.nullable))


def _count_rows(connection: Connection, table: Table) -> int:
    return int(connection.execute(select(func.count()).select_from(table)).scalar_one())


def _validate_primary_keys(
    connection: Connection, metadata: MetaData, table_names: tuple[str, ...]
) -> None:
    for table_name in table_names:
        table = metadata.tables[table_name]
        primary_key_columns = tuple(table.primary_key.columns)
        if not primary_key_columns:
            raise DatabaseMigrationError(f"表 {table_name} 没有主键，拒绝迁移")

        null_primary_key = (
            select(1)
            .select_from(table)
            .where(or_(*(column.is_(None) for column in primary_key_columns)))
            .limit(1)
        )
        if connection.execute(null_primary_key).first() is not None:
            raise DatabaseMigrationError(f"表 {table_name} 存在空主键")

        duplicate_primary_key = (
            select(*primary_key_columns, func.count().label("row_count"))
            .select_from(table)
            .group_by(*primary_key_columns)
            .having(func.count() > 1)
            .limit(1)
        )
        if connection.execute(duplicate_primary_key).first() is not None:
            raise DatabaseMigrationError(f"表 {table_name} 存在重复主键")


def _validate_foreign_keys(
    connection: Connection, metadata: MetaData, table_names: tuple[str, ...]
) -> None:
    for table_name in table_names:
        table = metadata.tables[table_name]
        for constraint_index, constraint in enumerate(table.foreign_key_constraints):
            elements = tuple(constraint.elements)
            parent_table = elements[0].column.table
            parent_alias = parent_table.alias(f"_openfic_fk_parent_{constraint_index}")
            matches = and_(
                *(
                    element.parent == parent_alias.c[element.column.name]
                    for element in elements
                )
            )
            all_values_present = and_(
                *(element.parent.is_not(None) for element in elements)
            )
            parent_exists = (
                select(1)
                .select_from(parent_alias)
                .where(matches)
                .correlate(table)
                .exists()
            )
            violation = (
                select(1)
                .select_from(table)
                .where(and_(all_values_present, ~parent_exists))
                .limit(1)
            )
            if connection.execute(violation).first() is not None:
                raise DatabaseMigrationError(f"表 {table_name} 存在无法解析的外键引用")


def _collect_orphaned_foreign_key_repairs(
    connection: Connection,
    metadata: MetaData,
    table_names: tuple[str, ...],
) -> tuple[_ForeignKeyRepairs, _ForeignKeyDeletions]:
    repairs: _ForeignKeyRepairs = {}
    deletions: _ForeignKeyDeletions = {}

    while True:
        changed = False
        for table_name in table_names:
            table = metadata.tables[table_name]
            primary_key_columns = tuple(table.primary_key.columns)
            if not primary_key_columns:
                raise DatabaseMigrationError(
                    f"表 {table_name} 没有主键，无法处理悬空外键"
                )
            deleted_keys = deletions.get(table_name, set())
            for constraint_index, constraint in enumerate(table.foreign_key_constraints):
                elements = tuple(constraint.elements)
                parent_table = elements[0].column.table
                parent_alias = parent_table.alias(
                    f"_openfic_repair_parent_{table_name}_{constraint_index}"
                )
                matches = and_(
                    *(
                        element.parent == parent_alias.c[element.column.name]
                        for element in elements
                    )
                )
                all_values_present = and_(
                    *(element.parent.is_not(None) for element in elements)
                )
                parent_exists = (
                    select(1)
                    .select_from(parent_alias)
                    .where(matches)
                    .correlate(table)
                    .exists()
                )
                missing_parent = ~parent_exists
                deleted_parent_exists = None
                parent_deleted_keys = deletions.get(parent_table.name, set())
                if parent_deleted_keys:
                    deleted_parent_match = or_(
                        *(
                            and_(
                                *(
                                    parent_alias.c[element.column.name] == value
                                    for element, value in zip(elements, key)
                                )
                            )
                            for key in parent_deleted_keys
                        )
                    )
                    deleted_parent_exists = (
                        select(1)
                        .select_from(parent_alias)
                        .where(and_(matches, deleted_parent_match))
                        .correlate(table)
                        .exists()
                    )
                parent_violation = (
                    or_(missing_parent, deleted_parent_exists)
                    if deleted_parent_exists is not None
                    else missing_parent
                )
                conditions = [all_values_present, parent_violation]
                if deleted_keys:
                    already_deleted = or_(
                        *(
                            and_(
                                *(
                                    column == value
                                    for column, value in zip(
                                        primary_key_columns, key
                                    )
                                )
                            )
                            for key in deleted_keys
                        )
                    )
                    conditions.append(~already_deleted)
                violation = (
                    select(*primary_key_columns)
                    .select_from(table)
                    .where(and_(*conditions))
                )
                rows = connection.execute(violation).all()
                if not rows:
                    continue

                local_columns = {element.parent.name for element in elements}
                can_repair = all(
                    table.c[column_name].nullable for column_name in local_columns
                )
                for row in rows:
                    primary_key = tuple(row)
                    if can_repair:
                        repaired_columns = repairs.setdefault(table_name, {}).setdefault(
                            primary_key, set()
                        )
                        before = len(repaired_columns)
                        repaired_columns.update(local_columns)
                        changed |= len(repaired_columns) != before
                    else:
                        table_deletions = deletions.setdefault(table_name, set())
                        if primary_key not in table_deletions:
                            table_deletions.add(primary_key)
                            repairs.get(table_name, {}).pop(primary_key, None)
                            changed = True
        if not changed:
            return repairs, deletions


def _database_stats(
    connection: Connection,
    metadata: MetaData,
    table_names: tuple[str, ...],
    repairs: _ForeignKeyRepairs | None = None,
    deletions: _ForeignKeyDeletions | None = None,
) -> _DatabaseStats:
    row_counts = {
        table_name: _count_rows(connection, metadata.tables[table_name])
        - len((deletions or {}).get(table_name, set()))
        for table_name in table_names
    }
    checksum = _database_checksum(connection, metadata, table_names, repairs, deletions)
    return _DatabaseStats(row_counts=row_counts, checksum=checksum)


def _normalize_decimal(value: object) -> dict[str, str]:
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        return {"type": "number", "value": str(value)}
    if decimal_value.is_zero():
        normalized = "0"
    else:
        normalized = format(decimal_value.normalize(), "f")
    return {"type": "decimal", "value": normalized}


def normalize_checksum_value(
    value: object, column_type: object | None = None
) -> object:
    """将跨方言值转换为稳定、可 JSON 序列化的校验值。"""
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(column_type, Boolean):
        return {"type": "boolean", "value": bool(value)}
    if isinstance(column_type, (Integer, BigInteger)):
        integer_value = (
            int(value) if isinstance(value, (bool, int)) else int(str(value))
        )
        return {"type": "integer", "value": integer_value}
    if isinstance(column_type, (Numeric, Float)):
        return _normalize_decimal(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"type": "bytes", "value": bytes(value).hex()}
    if isinstance(value, datetime):
        normalized_datetime = value
        if normalized_datetime.tzinfo is None:
            normalized_datetime = normalized_datetime.replace(tzinfo=UTC)
        else:
            normalized_datetime = normalized_datetime.astimezone(UTC)
        return {
            "type": "datetime",
            "value": normalized_datetime.isoformat(timespec="microseconds"),
        }
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, Decimal):
        return _normalize_decimal(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return {"type": "float", "value": str(value)}
        return _normalize_decimal(value)
    if isinstance(value, int):
        if value in {0, 1}:
            return {"type": "boolean", "value": bool(value)}
        return {"type": "integer", "value": value}
    if isinstance(value, Mapping):
        return {
            "type": "object",
            "value": {
                str(key): normalize_checksum_value(item)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            },
        }
    if isinstance(value, (list, tuple)):
        return {
            "type": "array",
            "value": [normalize_checksum_value(item) for item in value],
        }
    if isinstance(value, str):
        return {"type": "string", "value": value}
    return {"type": type(value).__name__, "value": str(value)}


def _encode_checksum_row(table: Table, row: Mapping[str, object]) -> bytes:
    normalized = [
        [
            column.name,
            normalize_checksum_value(row[column.name], column.type),
        ]
        for column in sorted(table.columns, key=lambda item: item.name)
    ]
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def checksum_rows(
    connection: Connection,
    table: Table,
    batch_size: int = _BATCH_SIZE,
    repairs: dict[tuple[object, ...], set[str]] | None = None,
    deletions: set[tuple[object, ...]] | None = None,
) -> str:
    """按行摘要汇总一张表的逻辑 checksum，避免依赖数据库排序规则。"""
    row_digests: list[bytes] = []
    result = connection.execute(select(table)).mappings()
    for rows in result.partitions(batch_size):
        for row in rows:
            row_values = dict(row)
            if _primary_key_value(table, row_values) in (deletions or set()):
                continue
            repaired_columns = (repairs or {}).get(
                _primary_key_value(table, row_values), set()
            )
            for column_name in repaired_columns:
                row_values[column_name] = None
            row_digests.append(
                hashlib.sha256(
                    _encode_checksum_row(table, cast(Mapping[str, object], row_values))
                ).digest()
            )
    digest = hashlib.sha256()
    for row_digest in sorted(row_digests):
        digest.update(row_digest)
    return digest.hexdigest()


def _primary_key_value(table: Table, row: Mapping[str, object]) -> tuple[object, ...]:
    return tuple(row[column.name] for column in table.primary_key.columns)


def _coerce_value(
    value: object,
    source_column: Column[Any],
    target_column: Column[Any],
) -> object:
    if not isinstance(value, datetime):
        return value
    if not isinstance(source_column.type, DateTime) or not isinstance(
        target_column.type, DateTime
    ):
        return value

    has_timezone = value.tzinfo is not None and value.utcoffset() is not None
    if target_column.type.timezone:
        return value.astimezone(UTC) if has_timezone else value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(tzinfo=None) if has_timezone else value


def _database_checksum(
    connection: Connection,
    metadata: MetaData,
    table_names: tuple[str, ...],
    repairs: _ForeignKeyRepairs | None = None,
    deletions: _ForeignKeyDeletions | None = None,
) -> str:
    digest = hashlib.sha256()
    for table_name in sorted(table_names):
        digest.update(table_name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(
            checksum_rows(
                connection,
                metadata.tables[table_name],
                repairs=(repairs or {}).get(table_name),
                deletions=(deletions or {}).get(table_name),
            ).encode("ascii")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _has_path(graph: dict[str, set[str]], start: str, goal: str) -> bool:
    pending = [start]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == goal:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(graph[current] - visited)
    return False


def _import_plan(
    metadata: MetaData,
    table_names: tuple[str, ...],
) -> tuple[tuple[str, ...], dict[str, frozenset[str]]]:
    _validate_foreign_key_definitions(metadata, table_names, "目标")
    table_set = set(table_names)
    graph = {table_name: set() for table_name in table_names}
    constraints: list[tuple[str, ForeignKeyConstraint, str]] = []
    for table_name in table_names:
        table = metadata.tables[table_name]
        for constraint in table.foreign_key_constraints:
            remote_table = next(iter(constraint.elements)).column.table.name
            if remote_table not in table_set:
                raise DatabaseMigrationError(
                    f"表 {table_name} 的外键目标表不存在: {remote_table}"
                )
            graph[table_name].add(remote_table)
            constraints.append((table_name, constraint, remote_table))

    dependency_graph = {
        table_name: set(dependencies) for table_name, dependencies in graph.items()
    }
    deferred_columns: dict[str, set[str]] = {
        table_name: set() for table_name in table_names
    }
    for table_name, constraint, remote_table in constraints:
        is_cycle = table_name == remote_table or _has_path(
            dependency_graph,
            remote_table,
            table_name,
        )
        if not is_cycle:
            continue
        table = metadata.tables[table_name]
        local_columns = tuple(element.parent.name for element in constraint.elements)
        non_nullable = [
            column for column in local_columns if not table.c[column].nullable
        ]
        if non_nullable:
            raise DatabaseMigrationError(
                f"检测到不可安全两阶段导入的循环外键: {table_name}({', '.join(non_nullable)})"
            )
        deferred_columns[table_name].update(local_columns)
        graph[table_name].discard(remote_table)

    remaining = {
        table_name: set(dependencies) for table_name, dependencies in graph.items()
    }
    ordered_tables: list[str] = []
    while remaining:
        ready = sorted(
            table_name
            for table_name, dependencies in remaining.items()
            if not dependencies
        )
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise DatabaseMigrationError(f"检测到无法安全导入的循环依赖: {cycle}")
        for table_name in ready:
            ordered_tables.append(table_name)
            remaining.pop(table_name)
        for dependencies in remaining.values():
            dependencies.difference_update(ready)

    return tuple(ordered_tables), {
        table_name: frozenset(columns)
        for table_name, columns in deferred_columns.items()
        if columns
    }


def _copy_table_rows(
    source_connection: Connection,
    target_connection: Connection,
    source_table: Table,
    target_table: Table,
    deferred_columns: frozenset[str],
    repairs: dict[tuple[object, ...], set[str]] | None = None,
    deletions: set[tuple[object, ...]] | None = None,
    batch_size: int = _BATCH_SIZE,
) -> int:
    column_names = tuple(target_table.c.keys())
    copied_rows = 0
    result = source_connection.execute(select(source_table)).mappings()
    for rows in result.partitions(batch_size):
        values = []
        for row in rows:
            row_values = dict(row)
            primary_key = _primary_key_value(source_table, row_values)
            if primary_key in (deletions or set()):
                continue
            repaired_columns = (repairs or {}).get(primary_key, set())
            values.append(
                {
                    column_name: (
                        None
                        if column_name in deferred_columns
                        or column_name in repaired_columns
                        else _coerce_value(
                            row[column_name],
                            source_table.c[column_name],
                            target_table.c[column_name],
                        )
                    )
                    for column_name in column_names
                }
            )
        if values:
            target_connection.execute(target_table.insert(), values)
            copied_rows += len(values)
    return copied_rows


def _restore_deferred_foreign_keys(
    source_connection: Connection,
    target_connection: Connection,
    source_table: Table,
    target_table: Table,
    deferred_columns: frozenset[str],
    repairs: dict[tuple[object, ...], set[str]] | None = None,
    deletions: set[tuple[object, ...]] | None = None,
    batch_size: int = _BATCH_SIZE,
) -> None:
    if not deferred_columns:
        return
    primary_key_columns = tuple(target_table.primary_key.columns)
    if not primary_key_columns:
        raise DatabaseMigrationError(
            f"表 {target_table.name} 没有主键，无法恢复循环外键"
        )

    primary_key_bind_names = tuple(
        f"_openfic_pk_{index}" for index, _ in enumerate(primary_key_columns)
    )
    value_bind_names = {
        column_name: f"_openfic_fk_{index}"
        for index, column_name in enumerate(sorted(deferred_columns))
    }
    update_statement = (
        target_table.update()
        .where(
            and_(
                *(
                    target_table.c[column.name] == bindparam(bind_name)
                    for column, bind_name in zip(
                        primary_key_columns, primary_key_bind_names
                    )
                )
            )
        )
        .values(
            {
                column_name: bindparam(bind_name)
                for column_name, bind_name in value_bind_names.items()
            }
        )
    )

    result = source_connection.execute(select(source_table)).mappings()
    for rows in result.partitions(batch_size):
        values = []
        for row in rows:
            row_values = dict(row)
            primary_key = _primary_key_value(source_table, row_values)
            if primary_key in (deletions or set()):
                continue
            repaired_columns = (repairs or {}).get(primary_key, set())
            item = {
                bind_name: row[column.name]
                for column, bind_name in zip(
                    primary_key_columns, primary_key_bind_names
                )
            }
            item.update(
                {
                    bind_name: _coerce_value(
                        row[column_name],
                        source_table.c[column_name],
                        target_table.c[column_name],
                    )
                    for column_name, bind_name in value_bind_names.items()
                    if column_name not in repaired_columns
                }
            )
            for column_name, bind_name in value_bind_names.items():
                if column_name in repaired_columns:
                    item[bind_name] = None
            values.append(item)
        if values:
            target_connection.execute(update_statement, values)


def _upgrade_target_schema(
    target_url: str, connection: Connection | None = None
) -> None:
    config = _create_alembic_config(target_url, connection)
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        raise _wrap_error(
            "目标数据库 Alembic upgrade head 失败，未绕过迁移",
            exc,
            (target_url,),
        ) from exc


def _check_target_is_empty(
    connection: Connection,
    target_metadata: MetaData,
    source_table_names: tuple[str, ...],
) -> None:
    target_table_names = set(_business_table_names(target_metadata))
    unknown_tables = target_table_names - set(source_table_names)
    if unknown_tables:
        raise DatabaseMigrationError(
            f"目标数据库存在源 schema 未定义的业务表: {', '.join(sorted(unknown_tables))}"
        )
    for table_name in sorted(target_table_names):
        row_count = _count_rows(connection, target_metadata.tables[table_name])
        if row_count:
            raise DatabaseMigrationError(
                f"目标库包含业务数据（表 {table_name} 有 {row_count} 行），拒绝覆盖"
            )


def migrate_database(
    *,
    target_url: str,
    source_url: str | None = None,
    repair_orphaned_references: bool = False,
) -> MigrationReport:
    """将 Alembic 管理的主业务库迁移到空目标库。"""
    resolved_source_url = resolve_source_url(source_url)
    source_sync_url, source_dialect = _prepare_database_url(resolved_source_url, "源")
    target_sync_url, target_dialect = _prepare_database_url(target_url, "目标")
    try:
        if make_url(source_sync_url).render_as_string(hide_password=True) == make_url(
            target_sync_url
        ).render_as_string(hide_password=True):
            raise DatabaseMigrationError("源数据库和目标数据库不能相同")
    except DatabaseMigrationError:
        raise
    except Exception as exc:
        raise _wrap_error(
            "无法比较源/目标数据库 URL", exc, (resolved_source_url, target_url)
        ) from exc

    source_engine: Engine | None = None
    target_engine: Engine | None = None
    source_repairs: _ForeignKeyRepairs = {}
    source_deletions: _ForeignKeyDeletions = {}
    try:
        source_engine, _ = _create_database_engine(source_sync_url, "源")
        target_engine, _ = _create_database_engine(target_sync_url, "目标")
        with source_engine.connect() as source_connection:
            _validate_source_revision(source_connection, source_sync_url)
            source_metadata = _reflect_metadata(
                source_connection, "源", source_sync_url
            )
            source_table_names = _business_table_names(source_metadata)
            if not source_table_names:
                raise DatabaseMigrationError("源数据库没有 Alembic 管理的业务表")
            _validate_foreign_key_definitions(source_metadata, source_table_names, "源")
            _validate_primary_keys(
                source_connection, source_metadata, source_table_names
            )
            if repair_orphaned_references:
                source_repairs, source_deletions = _collect_orphaned_foreign_key_repairs(
                    source_connection,
                    source_metadata,
                    source_table_names,
                )
            else:
                _validate_foreign_keys(
                    source_connection, source_metadata, source_table_names
                )
            source_stats = _database_stats(
                source_connection,
                source_metadata,
                source_table_names,
                source_repairs,
                source_deletions,
            )

            with target_engine.connect() as target_connection:
                initial_target_metadata = _reflect_metadata(
                    target_connection,
                    "目标",
                    target_sync_url,
                )
                _check_target_is_empty(
                    target_connection,
                    initial_target_metadata,
                    source_table_names,
                )
                target_connection.rollback()
                _upgrade_target_schema(target_sync_url, target_connection)
                target_connection.commit()

                target_metadata = _reflect_metadata(
                    target_connection,
                    "目标",
                    target_sync_url,
                )
                _validate_schema(source_metadata, target_metadata, source_table_names)
                target_table_names = _business_table_names(target_metadata)
                ordered_tables, deferred_columns = _import_plan(
                    target_metadata,
                    target_table_names,
                )

                target_connection.rollback()
                with target_connection.begin():
                    if target_dialect == "sqlite":
                        target_connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                    for table_name in ordered_tables:
                        _copy_table_rows(
                            source_connection,
                            target_connection,
                            source_metadata.tables[table_name],
                            target_metadata.tables[table_name],
                            deferred_columns.get(table_name, frozenset()),
                            source_repairs.get(table_name),
                            source_deletions.get(table_name),
                        )
                    for table_name in ordered_tables:
                        _restore_deferred_foreign_keys(
                            source_connection,
                            target_connection,
                            source_metadata.tables[table_name],
                            target_metadata.tables[table_name],
                            deferred_columns.get(table_name, frozenset()),
                            source_repairs.get(table_name),
                            source_deletions.get(table_name),
                        )
                    _validate_primary_keys(
                        target_connection, target_metadata, target_table_names
                    )
                    _validate_foreign_keys(
                        target_connection, target_metadata, target_table_names
                    )
                    target_stats = _database_stats(
                        target_connection,
                        target_metadata,
                        target_table_names,
                    )
                    if target_stats.row_counts != source_stats.row_counts:
                        raise DatabaseMigrationError("迁移后每表行数校验失败")
                    if target_stats.checksum != source_stats.checksum:
                        raise DatabaseMigrationError("迁移后逻辑 checksum 校验失败")

                return MigrationReport(
                    source_dialect=source_dialect,
                    target_dialect=target_dialect,
                    table_count=len(source_table_names),
                    row_count=sum(source_stats.row_counts.values()),
                    checksum=source_stats.checksum,
                    repaired_foreign_key_values=sum(
                        len(column_names)
                        for table_repairs in source_repairs.values()
                        for column_names in table_repairs.values()
                    ),
                    deleted_orphaned_rows=sum(
                        len(row_keys) for row_keys in source_deletions.values()
                    ),
                )
    except DatabaseMigrationError:
        raise
    except Exception as exc:
        raise _wrap_error(
            "数据库迁移失败",
            exc,
            (resolved_source_url, target_url),
        ) from exc
    finally:
        if source_engine is not None:
            source_engine.dispose()
        if target_engine is not None:
            target_engine.dispose()
