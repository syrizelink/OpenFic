from datetime import UTC, datetime
from decimal import Decimal
from importlib import import_module
from io import StringIO
import os
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from alembic import command
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
from app.storage.models.project import Project
from app.storage.models.llm_audit_log import LLMAuditLog


def _run_migration_operation(connection, operation) -> None:
    migration_context = MigrationContext.configure(connection)
    with Operations.context(migration_context):
        operation()


def _load_revisions_task_foreign_key_migration():
    return import_module(
        "app.storage.migrations.versions.1028_postgresql_backend_repairs"
    )


def _postgresql_migration_url() -> str:
    database_url = os.getenv("OPENFIC_TEST_DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("Set OPENFIC_TEST_DATABASE_URL to test PostgreSQL")
    return database_url


def _foreign_key_snapshot(connection, table_names):
    return {
        table_name: tuple(
            sorted(
                (
                    foreign_key.get("name"),
                    tuple(foreign_key.get("constrained_columns") or ()),
                    foreign_key.get("referred_table"),
                    tuple(foreign_key.get("referred_columns") or ()),
                    (foreign_key.get("options") or {}).get("ondelete"),
                )
                for foreign_key in inspect(connection).get_foreign_keys(table_name)
            )
        )
        for table_name in table_names
    }


def _check_constraint_snapshot(connection):
    return tuple(
        sorted(
            (
                table_name,
                constraint.get("name"),
                constraint.get("sqltext"),
            )
            for table_name in ("character_relationships",)
            for constraint in inspect(connection).get_check_constraints(table_name)
        )
    )


def _generate_offline_migration_sql(database_url: str, *, downgrade: bool) -> str:
    output = StringIO()
    config = database_migration._create_alembic_config(database_url)
    config.output_buffer = output
    if downgrade:
        command.downgrade(config, "1028:1027", sql=True)
    else:
        command.upgrade(config, "1027:1028", sql=True)
    return output.getvalue()


def _execute_offline_migration_sql(connection, sql: str) -> None:
    assert sql.startswith("BEGIN;\n")
    assert sql.rstrip().endswith("COMMIT;")
    body = sql[len("BEGIN;\n") :]
    body = body[: body.rfind("COMMIT;")]
    connection.exec_driver_sql(body.replace("%", "%%"))


def test_character_order_migration_preserves_relationships_and_snapshots():
    database_url = os.getenv("OPENFIC_TEST_DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("Set OPENFIC_TEST_DATABASE_URL to test PostgreSQL")
    migration = import_module(
        "app.storage.migrations.versions.1028_postgresql_backend_repairs"
    )
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            schema = f"character_migration_{uuid4().hex}"
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            connection.execute(text("CREATE COLLATION id_locale (provider = icu, locale = 'en-US')"))
            tables = ("character_relationships", "revision_character_relationship_snapshots")
            for table_name in tables:
                check = ", CHECK (source_character_id < target_character_id)" if table_name == tables[0] else ""
                connection.execute(text(
                    f"CREATE TABLE {table_name} (id TEXT PRIMARY KEY, "
                    "source_character_id TEXT COLLATE id_locale, "
                    f"target_character_id TEXT COLLATE id_locale{check})"
                ))
                connection.execute(text(
                    f"INSERT INTO {table_name} VALUES ('existing', 'a', 'Z')"
                ))
                if table_name != tables[0]:
                    connection.execute(text(
                        f"INSERT INTO {table_name} VALUES ('empty', NULL, NULL)"
                    ))
            _run_migration_operation(connection, lambda: migration._repair_character_relationship_order(connection))
            for table_name in tables:
                assert connection.execute(text(
                    f"SELECT source_character_id, target_character_id FROM {table_name} WHERE id='existing'"
                )).one() == ("Z", "a")
            connection.execute(text("INSERT INTO character_relationships VALUES ('new', 'A', 'a')"))
            assert connection.execute(text(
                "SELECT source_character_id, target_character_id FROM revision_character_relationship_snapshots WHERE id='empty'"
            )).one() == (None, None)
            _run_migration_operation(connection, lambda: migration._restore_character_relationship_order(connection))
            for table_name in tables:
                assert connection.execute(text(
                    f"SELECT source_character_id, target_character_id FROM {table_name} WHERE id='existing'"
                )).one() == ("a", "Z")
            assert connection.execute(text(
                "SELECT source_character_id, target_character_id FROM character_relationships WHERE id='new'"
            )).one() == ("a", "A")
            _run_migration_operation(connection, lambda: migration._repair_character_relationship_order(connection))
            checks = inspect(connection).get_check_constraints(tables[0])
            assert len(checks) == 1
            assert 'COLLATE "C"' in checks[0]["sqltext"]
            transaction.rollback()
    finally:
        engine.dispose()


def test_postgresql_1028_offline_sql_executes_like_online_upgrade_and_downgrade():
    database_url = _postgresql_migration_url()
    engine = create_engine(database_url)
    table_names = ("revisions", "agent_audit_logs", "commits")
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                schema = f"migration_sql_{uuid4().hex}"
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                config = database_migration._create_alembic_config(
                    database_url, connection
                )
                command.upgrade(config, "1027")

                initial_foreign_keys = _foreign_key_snapshot(connection, table_names)
                initial_checks = _check_constraint_snapshot(connection)
                assert not any(
                    item[2] == "tasks" for item in initial_foreign_keys["revisions"]
                )
                assert next(
                    item
                    for item in initial_foreign_keys["agent_audit_logs"]
                    if item[1] == ("task_id",)
                )[0] == "agent_audit_logs_task_id_fkey"
                assert next(
                    item
                    for item in initial_foreign_keys["commits"]
                    if item[1] == ("chapter_id",)
                )[0] == "commits_chapter_id_fkey"

                upgrade_sql = _generate_offline_migration_sql(
                    database_url, downgrade=False
                )
                downgrade_sql = _generate_offline_migration_sql(
                    database_url, downgrade=True
                )
                for default_name in (
                    "agent_audit_logs_task_id_fkey",
                    "agent_audit_logs_revision_id_fkey",
                    "agent_audit_logs_chapter_id_fkey",
                    "agent_audit_logs_project_id_fkey",
                    "commits_chapter_id_fkey",
                    "commits_revision_id_fkey",
                ):
                    assert f"DROP CONSTRAINT {default_name}" in upgrade_sql

                online_state = connection.begin_nested()
                command.upgrade(config, "1028")
                online_upgrade_foreign_keys = _foreign_key_snapshot(
                    connection, table_names
                )
                online_upgrade_checks = _check_constraint_snapshot(connection)
                command.downgrade(config, "1027")
                online_downgrade_foreign_keys = _foreign_key_snapshot(
                    connection, table_names
                )
                online_downgrade_checks = _check_constraint_snapshot(connection)
                online_state.rollback()

                _execute_offline_migration_sql(connection, upgrade_sql)
                assert (
                    connection.execute(text("SELECT version_num FROM alembic_version"))
                    .scalar_one()
                    == "1028"
                )
                assert _foreign_key_snapshot(connection, table_names) == (
                    online_upgrade_foreign_keys
                )
                assert _check_constraint_snapshot(connection) == online_upgrade_checks

                _execute_offline_migration_sql(connection, downgrade_sql)
                assert (
                    connection.execute(text("SELECT version_num FROM alembic_version"))
                    .scalar_one()
                    == "1027"
                )
                assert _foreign_key_snapshot(connection, table_names) == (
                    initial_foreign_keys
                )
                assert _check_constraint_snapshot(connection) == initial_checks
                assert online_downgrade_foreign_keys == initial_foreign_keys
                assert online_downgrade_checks == initial_checks
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_published_schema_upgrades_to_head_and_keeps_existing_data(tmp_path, database):
    database_url = f"sqlite:///{tmp_path / 'published.db'}"
    if database == "postgresql":
        database_url = os.getenv("OPENFIC_TEST_DATABASE_URL", "")
        if not database_url.startswith("postgresql"):
            pytest.skip("Set OPENFIC_TEST_DATABASE_URL to test PostgreSQL")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            if database == "postgresql":
                schema = f"published_migration_{uuid4().hex}"
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = database_migration._create_alembic_config(database_url, connection)
            command.upgrade(config, "1026")
            connection.execute(Project.__table__.insert(), {"id": "published-project", "title": "published"})
            audit_table = Table("agent_audit_logs", MetaData(), autoload_with=connection)
            detail = "\u4e2d\u6587 audit"
            audit_values = {
                column.name: column.default.arg
                for column in LLMAuditLog.__table__.columns
                if column.default is not None and column.default.is_scalar
                and column.name in audit_table.c
            }
            connection.execute(audit_table.insert(), {
                **audit_values, "id": "published-audit", "project_id": "published-project",
                "operation": "chat", "model_id": "test", "status": "success",
                "created_at": datetime(2026, 10, 13), "response_content": detail,
            })
            command.upgrade(config, "1027")
            assert connection.execute(text(
                "SELECT has_details, detail_bytes FROM agent_audit_logs WHERE id='published-audit'"
            )).one() == (True, len(detail.encode("utf-8")))
            original_foreign_keys = {
                table_name: {
                    (tuple(fk["constrained_columns"]), fk["referred_table"],
                     tuple(fk["referred_columns"]), fk["options"].get("ondelete"))
                    for fk in inspect(connection).get_foreign_keys(table_name)
                }
                for table_name in ("revisions", "commits", "agent_audit_logs")
            }
            command.upgrade(config, "head")
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "1030"
            assert connection.execute(text(
                "SELECT response_content, has_details, detail_bytes FROM agent_audit_logs WHERE id='published-audit'"
            )).one() == (detail, True, len(detail.encode("utf-8")))
            assert connection.execute(text("SELECT title FROM projects WHERE id='published-project'")).scalar_one() == "published"
            checks = inspect(connection).get_check_constraints("character_relationships")
            assert len(checks) == 1
            if database == "postgresql":
                assert 'COLLATE "C"' in checks[0]["sqltext"]
            else:
                assert "COLLATE" not in checks[0]["sqltext"]
            revision_foreign_keys = inspect(connection).get_foreign_keys("revisions")
            assert any(fk["constrained_columns"] == ["task_id"] for fk in revision_foreign_keys)
            commit_foreign_keys = inspect(connection).get_foreign_keys("commits")
            assert not any(fk["constrained_columns"] == ["chapter_id"] for fk in commit_foreign_keys)
            assert next(fk for fk in commit_foreign_keys if fk["constrained_columns"] == ["revision_id"])["options"]["ondelete"] == "CASCADE"
            assert {
                fk["constrained_columns"][0]: fk["options"].get("ondelete")
                for fk in inspect(connection).get_foreign_keys("agent_audit_logs")
            } == {"task_id": "SET NULL", "revision_id": "SET NULL", "chapter_id": "SET NULL", "project_id": "CASCADE"}
            command.downgrade(config, "1027")
            for table_name, expected in original_foreign_keys.items():
                assert {
                    (tuple(fk["constrained_columns"]), fk["referred_table"],
                     tuple(fk["referred_columns"]), fk["options"].get("ondelete"))
                    for fk in inspect(connection).get_foreign_keys(table_name)
                } == expected
            assert connection.execute(text(
                "SELECT response_content, has_details, detail_bytes FROM agent_audit_logs WHERE id='published-audit'"
            )).one() == (detail, True, len(detail.encode("utf-8")))
            command.upgrade(config, "head")
            transaction.rollback()
    finally:
        engine.dispose()


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
    for table_name in (
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
        "checkpoint_migrations",
        "writes",
        "openfic_checkpoint_migrations",
    ):
        Table(table_name, metadata, Column("id", String, primary_key=True))
    Table("projects", metadata, Column("id", String, primary_key=True))
    Table("custom_business_table", metadata, Column("id", String, primary_key=True))

    assert database_migration._business_table_names(metadata) == (
        "custom_business_table",
        "projects",
    )


def test_task_foreign_key_repair_rebuilds_sqlite_table_and_is_idempotent() -> None:
    migration = _load_revisions_task_foreign_key_migration()
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            _create_revisions_task_tables(connection, with_foreign_key=False)

            _run_migration_operation(connection, lambda: migration._repair_revisions_task_foreign_key(connection))
            _run_migration_operation(connection, lambda: migration._repair_revisions_task_foreign_key(connection))

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
                    migration._TASK_CONSTRAINT_NAME,
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
            _run_migration_operation(connection, lambda: migration._repair_revisions_task_foreign_key(connection))
            _run_migration_operation(connection, lambda: migration._restore_revisions_task_foreign_key(connection))
            assert inspect(connection).get_foreign_keys("revisions") == []

        engine.dispose()
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            _create_revisions_task_tables(connection, with_foreign_key=True)
            _run_migration_operation(connection, lambda: migration._repair_revisions_task_foreign_key(connection))
            _run_migration_operation(connection, lambda: migration._restore_revisions_task_foreign_key(connection))
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
        migration._repair_revisions_task_foreign_key(migration_context.bind)
        migration._restore_revisions_task_foreign_key(migration_context.bind)

    sql = output.getvalue()
    assert "ALTER TABLE revisions ADD CONSTRAINT" in sql
    assert "FOREIGN KEY(task_id) REFERENCES tasks (id)" in sql
    assert f"ALTER TABLE revisions DROP CONSTRAINT {migration._TASK_CONSTRAINT_NAME}" in sql


def test_1028_postgresql_offline_upgrade_and_downgrade_do_not_inspect_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_revisions_task_foreign_key_migration()
    output = StringIO()
    migration_context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    monkeypatch.setattr(
        migration.sa,
        "inspect",
        Mock(side_effect=AssertionError("offline migration must not inspect bind")),
    )

    with Operations.context(migration_context):
        migration.upgrade()
        migration.downgrade()

    sql = output.getvalue()
    assert (
        "ALTER TABLE revisions DROP CONSTRAINT IF EXISTS revisions_task_id_fkey"
        in sql
    )
    assert (
        f"ALTER TABLE revisions ADD CONSTRAINT {migration._TASK_CONSTRAINT_NAME}"
        in sql
    )
    assert (
        f"ALTER TABLE revisions DROP CONSTRAINT {migration._TASK_CONSTRAINT_NAME}"
        in sql
    )
    assert (
        f"ALTER TABLE commits DROP CONSTRAINT {migration._COMMIT_CHAPTER_CONSTRAINT_NAME}"
        in sql
    )


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


def test_schema_allows_target_string_columns_to_expand() -> None:
    source_metadata = MetaData()
    Table(
        "items",
        source_metadata,
        Column("id", String, primary_key=True),
        Column("mime_type", String(length=50), nullable=False),
    )
    target_metadata = MetaData()
    Table(
        "items",
        target_metadata,
        Column("id", String, primary_key=True),
        Column("mime_type", String(length=255), nullable=False),
    )

    database_migration._validate_schema(source_metadata, target_metadata, ("items",))


def test_schema_rejects_target_string_columns_to_shrink() -> None:
    source_metadata = MetaData()
    Table("items", source_metadata, Column("value", String(length=255)))
    target_metadata = MetaData()
    Table("items", target_metadata, Column("value", String(length=50)))

    with pytest.raises(database_migration.DatabaseMigrationError, match="列结构"):
        database_migration._validate_schema(source_metadata, target_metadata, ("items",))


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

    with pytest.raises(database_migration.OrphanedForeignKeyError, match="外键引用") as exc_info:
        database_migration.migrate_database(
            source_url=source_url,
            target_url=target_url,
        )

    error = str(exc_info.value)
    assert "--repair-orphaned-references" in error
    assert "NULL" in error
    assert "删除" in error
    assert "源库不修改" in error

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
