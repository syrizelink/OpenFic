from datetime import UTC, datetime
from decimal import Decimal
from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Float,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

import app.storage.database_migration as database_migration
from app.settings import to_sync_database_url


def _run_migration_operation(connection, operation) -> None:
    migration_context = MigrationContext.configure(connection)
    with Operations.context(migration_context):
        operation()


def _load_revisions_task_foreign_key_migration():
    return import_module(
        "app.storage.migrations.versions.1022_repair_revisions_task_foreign_key"
    )


def _create_revisions_task_tables(connection, *, with_foreign_key: bool) -> None:
    metadata = MetaData()
    tasks = Table("tasks", metadata, Column("id", String, primary_key=True))
    task_id_column = Column("task_id", String)
    if with_foreign_key:
        task_id_column.append_foreign_key(ForeignKey("tasks.id", name="existing_task_fk"))
    revisions = Table(
        "revisions",
        metadata,
        Column("id", String, primary_key=True),
        task_id_column,
    )
    metadata.create_all(connection)
    connection.execute(tasks.insert(), {"id": "task-1"})
    connection.execute(
        revisions.insert(),
        {"id": "revision-1", "task_id": "task-1"},
    )


def test_sync_database_url_converts_async_sqlite_only() -> None:
    assert (
        to_sync_database_url("sqlite+aiosqlite:////tmp/openfic.db")
        == "sqlite:////tmp/openfic.db"
    )
    database_url = "postgresql+psycopg://user:password@localhost/openfic"
    assert to_sync_database_url(database_url) == database_url


def test_business_table_names_exclude_runtime_maintenance_tables() -> None:
    metadata = MetaData()
    Table("alembic_version", metadata, Column("version_num", String))
    Table(
        "openfic_maintenance_migrations",
        metadata,
        Column("name", String, primary_key=True),
    )
    Table("projects", metadata, Column("id", String, primary_key=True))

    assert database_migration._business_table_names(metadata) == ("projects",)


def test_task_foreign_key_repair_rebuilds_sqlite_table_and_is_idempotent() -> None:
    migration = _load_revisions_task_foreign_key_migration()
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            _create_revisions_task_tables(connection, with_foreign_key=False)

            _run_migration_operation(connection, migration.upgrade)
            _run_migration_operation(connection, migration.upgrade)

            foreign_keys = inspect(connection).get_foreign_keys("revisions")
            assert [
                (
                    item["name"],
                    item["constrained_columns"],
                    item["referred_table"],
                    item["referred_columns"],
                )
                for item in foreign_keys
            ] == [
                (
                    migration.CONSTRAINT_NAME,
                    ["task_id"],
                    "tasks",
                    ["id"],
                )
            ]
            assert connection.execute(
                text("SELECT id, task_id FROM revisions")
            ).all() == [("revision-1", "task-1")]
    finally:
        engine.dispose()


def test_task_foreign_key_repair_downgrade_only_removes_repair_constraint() -> None:
    migration = _load_revisions_task_foreign_key_migration()
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            _create_revisions_task_tables(connection, with_foreign_key=False)
            _run_migration_operation(connection, migration.upgrade)
            _run_migration_operation(connection, migration.downgrade)
            assert inspect(connection).get_foreign_keys("revisions") == []

        engine.dispose()
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            _create_revisions_task_tables(connection, with_foreign_key=True)
            _run_migration_operation(connection, migration.upgrade)
            _run_migration_operation(connection, migration.downgrade)
            foreign_keys = inspect(connection).get_foreign_keys("revisions")
            assert len(foreign_keys) == 1
            assert foreign_keys[0]["name"] == "existing_task_fk"
    finally:
        engine.dispose()


def test_task_foreign_key_repair_compiles_for_postgresql_dialect() -> None:
    migration = _load_revisions_task_foreign_key_migration()
    output = StringIO()
    migration_context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )

    with Operations.context(migration_context):
        migration.upgrade()
        migration.downgrade()

    sql = output.getvalue()
    assert "ALTER TABLE revisions ADD CONSTRAINT" in sql
    assert "FOREIGN KEY(task_id) REFERENCES tasks (id)" in sql
    assert f"ALTER TABLE revisions DROP CONSTRAINT {migration.CONSTRAINT_NAME}" in sql


def test_resolve_source_url_uses_configured_database_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        database_migration,
        "settings",
        SimpleNamespace(database_sync_url="sqlite:////tmp/configured.db"),
    )

    assert database_migration.resolve_source_url(None) == "sqlite:////tmp/configured.db"
    assert database_migration.resolve_source_url("sqlite:////tmp/explicit.db") == (
        "sqlite:////tmp/explicit.db"
    )


def test_alembic_config_carries_explicit_database_url() -> None:
    database_url = "sqlite:////tmp/target.db"

    config = database_migration._create_alembic_config(database_url)

    assert (
        config.attributes[database_migration.ALEMBIC_DATABASE_URL_ATTRIBUTE]
        == database_url
    )


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:////tmp/openfic.db",
        "sqlite+aiosqlite:////tmp/openfic.db",
        "postgresql+psycopg://user:password@localhost/openfic",
    ],
)
def test_supported_database_urls_compile_with_sync_engine(database_url: str) -> None:
    sync_url = to_sync_database_url(database_url)

    engine = create_engine(sync_url)
    try:
        assert engine.dialect.name in {"sqlite", "postgresql"}
    finally:
        engine.dispose()


def test_checksum_normalizes_cross_dialect_scalar_values() -> None:
    assert database_migration.normalize_checksum_value(b"payload") == {
        "type": "bytes",
        "value": "7061796c6f6164",
    }
    assert database_migration.normalize_checksum_value(Decimal("1.00")) == (
        database_migration.normalize_checksum_value(Decimal("1"))
    )
    assert database_migration.normalize_checksum_value(False) == (
        database_migration.normalize_checksum_value(0)
    )
    assert database_migration.normalize_checksum_value(
        datetime(2026, 1, 1, 12, tzinfo=UTC)
    ) == database_migration.normalize_checksum_value(datetime(2026, 1, 1, 12))


def test_checksum_does_not_parse_json_strings() -> None:
    json_text = '{"b": 2, "a": 1}'

    assert database_migration.normalize_checksum_value(json_text) == {
        "type": "string",
        "value": json_text,
    }


def test_checksum_is_independent_of_database_row_order() -> None:
    metadata = MetaData()
    table = Table(
        "items",
        metadata,
        Column("id", String, primary_key=True),
        Column("value", String),
    )

    class Result:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self.rows = rows

        def mappings(self) -> "Result":
            return self

        def partitions(self, _batch_size: int):
            yield self.rows

    class Connection:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self.rows = rows

        def execute(self, _statement) -> Result:
            return Result(self.rows)

    rows = [{"id": "A", "value": "one"}, {"id": "a", "value": "two"}]

    assert database_migration.checksum_rows(Connection(rows), table) == (
        database_migration.checksum_rows(Connection(list(reversed(rows))), table)
    )


def test_schema_type_mismatch_is_rejected() -> None:
    source_metadata = MetaData()
    Table("items", source_metadata, Column("id", String, primary_key=True))
    target_metadata = MetaData()
    Table("items", target_metadata, Column("id", Integer, primary_key=True))

    with pytest.raises(database_migration.DatabaseMigrationError, match="列结构"):
        database_migration._validate_schema(
            source_metadata,
            target_metadata,
            ("items",),
        )


def test_float_precision_difference_between_dialects_is_portable() -> None:
    source_metadata = MetaData()
    Table(
        "items",
        source_metadata,
        Column("id", String, primary_key=True),
        Column("value", Float),
    )
    target_metadata = MetaData()
    Table(
        "items",
        target_metadata,
        Column("id", String, primary_key=True),
        Column("value", Float(precision=53)),
    )

    database_migration._validate_schema(
        source_metadata,
        target_metadata,
        ("items",),
    )


def test_postgresql_jsonb_schema_is_not_treated_as_portable_json() -> None:
    source_metadata = MetaData()
    Table("items", source_metadata, Column("payload", JSONB, nullable=False))
    target_metadata = MetaData()
    Table("items", target_metadata, Column("payload", JSON, nullable=False))

    with pytest.raises(database_migration.DatabaseMigrationError, match="列结构"):
        database_migration._validate_schema(
            source_metadata,
            target_metadata,
            ("items",),
        )


def test_datetime_timezone_flag_is_portable_across_sqlite_and_postgresql() -> None:
    source_metadata = MetaData()
    Table(
        "items",
        source_metadata,
        Column("id", String, primary_key=True),
        Column("created_at", DateTime(timezone=False), nullable=False),
    )
    target_metadata = MetaData()
    Table(
        "items",
        target_metadata,
        Column("id", String, primary_key=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )

    database_migration._validate_schema(
        source_metadata,
        target_metadata,
        ("items",),
    )


def test_datetime_values_are_normalized_for_target_timezone() -> None:
    source_metadata = MetaData()
    source_table = Table(
        "items",
        source_metadata,
        Column("id", String, primary_key=True),
        Column("created_at", DateTime(timezone=False), nullable=False),
    )
    target_metadata = MetaData()
    target_table = Table(
        "items",
        target_metadata,
        Column("id", String, primary_key=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )
    naive_value = datetime(2026, 1, 1, 12)

    normalized = database_migration._coerce_value(
        naive_value,
        source_table.c.created_at,
        target_table.c.created_at,
    )

    assert normalized == naive_value.replace(tzinfo=UTC)


def test_legacy_source_revision_is_rejected(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_url = f"sqlite:///{tmp_path / 'source.db'}"
    target_url = f"sqlite:///{tmp_path / 'target.db'}"
    engine = create_engine(source_url)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('1001')")
        )
    engine.dispose()
    upgrade = Mock()
    monkeypatch.setattr(database_migration, "_upgrade_target_schema", upgrade)

    with pytest.raises(database_migration.DatabaseMigrationError, match="legacy"):
        database_migration.migrate_database(
            source_url=source_url, target_url=target_url
        )

    upgrade.assert_not_called()


def test_database_error_redacts_sync_variant_of_async_url() -> None:
    error = database_migration._wrap_error(
        "数据库连接失败",
        RuntimeError("could not connect to postgresql+psycopg://user:secret@host/db"),
        ("postgresql+asyncpg://user:secret@host/db",),
    )

    assert "secret" not in str(error)
    assert "postgresql+psycopg://user" not in str(error)


def test_target_with_business_rows_is_rejected(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_url = f"sqlite:///{tmp_path / 'source.db'}"
    target_url = f"sqlite:///{tmp_path / 'target.db'}"
    metadata = MetaData()
    projects = Table(
        "projects",
        metadata,
        Column("id", String, primary_key=True),
    )
    monkeypatch.setattr(database_migration, "_validate_source_revision", lambda *_: None)
    for database_url in (source_url, target_url):
        engine = create_engine(database_url)
        metadata.create_all(engine)
        engine.dispose()

    target_engine = create_engine(target_url)
    with target_engine.begin() as connection:
        connection.execute(projects.insert(), {"id": "existing"})
    target_engine.dispose()

    with pytest.raises(
        database_migration.DatabaseMigrationError, match="目标库包含业务数据"
    ):
        database_migration.migrate_database(
            source_url=source_url,
            target_url=target_url,
        )


def test_migration_rolls_back_target_data_on_import_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_url = f"sqlite:///{tmp_path / 'source.db'}"
    target_url = f"sqlite:///{tmp_path / 'target.db'}"
    metadata = MetaData()
    parents = Table(
        "parents",
        metadata,
        Column("id", String, primary_key=True),
    )
    children = Table(
        "children",
        metadata,
        Column("id", String, primary_key=True),
        Column("parent_id", String, ForeignKey("parents.id"), nullable=False),
    )

    monkeypatch.setattr(database_migration, "_validate_source_revision", lambda *_: None)
    for database_url in (source_url, target_url):
        engine = create_engine(database_url)
        metadata.create_all(engine)
        engine.dispose()

    source_engine = create_engine(source_url)
    with source_engine.begin() as connection:
        connection.execute(parents.insert(), {"id": "parent"})
        connection.execute(children.insert(), {"id": "child", "parent_id": "parent"})
    source_engine.dispose()

    monkeypatch.setattr(
        database_migration,
        "_upgrade_target_schema",
        lambda _url, _connection=None: None,
    )
    original_copy = database_migration._copy_table_rows

    def copy_then_fail(*args, **kwargs):
        original_copy(*args, **kwargs)
        raise RuntimeError("forced import failure")

    monkeypatch.setattr(database_migration, "_copy_table_rows", copy_then_fail)

    with pytest.raises(
        database_migration.DatabaseMigrationError, match="forced import failure"
    ):
        database_migration.migrate_database(
            source_url=source_url, target_url=target_url
        )

    target_engine = create_engine(target_url)
    with target_engine.connect() as connection:
        assert (
            connection.execute(text("SELECT COUNT(*) FROM parents")).scalar_one() == 0
        )
        assert (
            connection.execute(text("SELECT COUNT(*) FROM children")).scalar_one() == 0
        )
    target_engine.dispose()


def test_migration_preserves_self_referencing_rows(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_url = f"sqlite:///{tmp_path / 'source.db'}"
    target_url = f"sqlite:///{tmp_path / 'target.db'}"
    metadata = MetaData()
    categories = Table(
        "categories",
        metadata,
        Column("id", String, primary_key=True),
        Column("parent_id", String, ForeignKey("categories.id"), nullable=True),
    )

    monkeypatch.setattr(database_migration, "_validate_source_revision", lambda *_: None)
    for database_url in (source_url, target_url):
        engine = create_engine(database_url)
        metadata.create_all(engine)
        engine.dispose()

    source_engine = create_engine(source_url)
    with source_engine.begin() as connection:
        connection.execute(
            categories.insert(),
            [{"id": "root", "parent_id": None}, {"id": "child", "parent_id": "root"}],
        )
    source_engine.dispose()

    monkeypatch.setattr(
        database_migration,
        "_upgrade_target_schema",
        lambda _url, _connection=None: None,
    )

    report = database_migration.migrate_database(
        source_url=source_url, target_url=target_url
    )

    assert report.row_count == 2
    target_engine = create_engine(target_url)
    with target_engine.connect() as connection:
        rows = connection.execute(
            select(categories.c.id, categories.c.parent_id).order_by(categories.c.id)
        ).all()
    target_engine.dispose()

    assert rows == [("child", "root"), ("root", None)]


def test_migration_can_repair_nullable_orphaned_foreign_keys(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_url = f"sqlite:///{tmp_path / 'source.db'}"
    target_url = f"sqlite:///{tmp_path / 'target.db'}"
    metadata = MetaData()
    _projects = Table("projects", metadata, Column("id", String, primary_key=True))
    audit_logs = Table(
        "agent_audit_logs",
        metadata,
        Column("id", String, primary_key=True),
        Column("project_id", String, ForeignKey("projects.id"), nullable=True),
    )

    monkeypatch.setattr(database_migration, "_validate_source_revision", lambda *_: None)
    for database_url in (source_url, target_url):
        engine = create_engine(database_url)
        metadata.create_all(engine)
        engine.dispose()

    source_engine = create_engine(source_url)
    with source_engine.begin() as connection:
        connection.execute(
            audit_logs.insert(),
            {"id": "audit-1", "project_id": "deleted-project"},
        )
    source_engine.dispose()

    monkeypatch.setattr(
        database_migration,
        "_upgrade_target_schema",
        lambda _url, _connection=None: None,
    )

    with pytest.raises(database_migration.DatabaseMigrationError, match="外键引用"):
        database_migration.migrate_database(
            source_url=source_url,
            target_url=target_url,
        )

    report = database_migration.migrate_database(
        source_url=source_url,
        target_url=target_url,
        repair_orphaned_references=True,
    )

    assert report.repaired_foreign_key_values == 1
    target_engine = create_engine(target_url)
    with target_engine.connect() as connection:
        assert connection.execute(
            select(audit_logs.c.id, audit_logs.c.project_id)
        ).all() == [("audit-1", None)]
    target_engine.dispose()


def test_migration_deletes_non_nullable_orphaned_rows(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_url = f"sqlite:///{tmp_path / 'source.db'}"
    target_url = f"sqlite:///{tmp_path / 'target.db'}"
    metadata = MetaData()
    _parents = Table("parents", metadata, Column("id", String, primary_key=True))
    required_children = Table(
        "required_children",
        metadata,
        Column("id", String, primary_key=True),
        Column("parent_id", String, ForeignKey("parents.id"), nullable=False),
    )

    monkeypatch.setattr(database_migration, "_validate_source_revision", lambda *_: None)
    for database_url in (source_url, target_url):
        engine = create_engine(database_url)
        metadata.create_all(engine)
        engine.dispose()

    source_engine = create_engine(source_url)
    with source_engine.begin() as connection:
        connection.execute(
            required_children.insert(),
            {"id": "orphan-child", "parent_id": "deleted-parent"},
        )
    source_engine.dispose()

    monkeypatch.setattr(
        database_migration,
        "_upgrade_target_schema",
        lambda _url, _connection=None: None,
    )

    report = database_migration.migrate_database(
        source_url=source_url,
        target_url=target_url,
        repair_orphaned_references=True,
    )

    assert report.deleted_orphaned_rows == 1
    target_engine = create_engine(target_url)
    with target_engine.connect() as connection:
        assert connection.execute(
            select(required_children.c.id)
        ).all() == []
    target_engine.dispose()
