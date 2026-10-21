import importlib
from io import StringIO
import os
from uuid import uuid4

from alembic import command
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, text

from app.storage.models.llm_audit_log import LLMAuditLog
from app.storage.migrations.postgresql_compat import upgrade_dashboard_metadata_indexes
from app.storage.database_migration import _create_alembic_config


def test_dashboard_compatibility_routes_only_postgresql_upgrade():
    migration = importlib.import_module(
        "app.storage.migrations.versions.1027_dashboard_metadata_indexes"
    )
    original_upgrade = migration.upgrade
    for dialect in ("postgresql", "sqlite", "postgresql"):
        if dialect == "sqlite":
            engine = create_engine("sqlite:///:memory:")
            try:
                with engine.begin() as connection:
                    config = _create_alembic_config("sqlite://", connection)
                    command.upgrade(config, "1026")
                    command.upgrade(config, "1027")
                    assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "1027"
                    assert {"has_details", "detail_bytes"} <= {
                        column["name"] for column in inspect(connection).get_columns("agent_audit_logs")
                    }
            finally:
                engine.dispose()
            assert migration.upgrade is original_upgrade
            continue
        output = StringIO()
        config = _create_alembic_config("postgresql+psycopg://localhost/unused")
        config.output_buffer = output
        command.upgrade(config, "1026:1027", sql=True)
        sql = output.getvalue()
        assert "UPDATE alembic_version SET version_num='1027'" in sql
        assert "CREATE INDEX ix_agent_audit_logs_detail_storage" in sql
        assert "THEN TRUE ELSE FALSE END" in sql
        assert "octet_length(convert_to(" in sql
        assert "BLOB" not in sql
        assert migration.upgrade is original_upgrade

    output = StringIO()
    config = _create_alembic_config("postgresql+psycopg://localhost/unused")
    config.output_buffer = output
    command.downgrade(config, "1027:1026", sql=True)
    assert "DROP COLUMN detail_bytes" in output.getvalue()
    assert "UPDATE agent_audit_logs" not in output.getvalue()

    output = StringIO()
    config = _create_alembic_config("postgresql+psycopg://localhost/unused")
    config.output_buffer = output
    command.stamp(config, "1027", sql=True)
    assert "INSERT INTO alembic_version" in output.getvalue()
    assert "UPDATE agent_audit_logs" not in output.getvalue()
    assert "CREATE INDEX" not in output.getvalue()


def test_dashboard_metadata_indexes_postgresql_offline_sql(monkeypatch):
    migration = importlib.import_module(
        "app.storage.migrations.versions.1027_dashboard_metadata_indexes"
    )
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    upgrade_dashboard_metadata_indexes(migration)
    sql = output.getvalue()
    assert "THEN TRUE ELSE FALSE END" in sql
    for column in migration.DETAIL_COLUMNS:
        assert f"{column} IS NOT NULL" in sql
        assert f"COALESCE(octet_length(convert_to({column}, 'UTF8')), 0)" in sql
    assert "BLOB" not in sql


@pytest.mark.parametrize("database", ["sqlite", "postgresql"])
def test_dashboard_metadata_indexes_migrate_existing_records(
    tmp_path, monkeypatch, database
):
    migration = importlib.import_module(
        "app.storage.migrations.versions.1027_dashboard_metadata_indexes"
    )
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    if database == "postgresql":
        database_url = os.getenv("OPENFIC_TEST_DATABASE_URL", "")
        if not database_url.startswith("postgresql"):
            pytest.skip("Set OPENFIC_TEST_DATABASE_URL to test PostgreSQL")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection, connection.begin() as transaction:
            if database == "postgresql":
                schema = f"audit_migration_{uuid4().hex}"
                connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            columns = {name for _, names in migration.INDEXES for name in names}
            columns.update(migration.DETAIL_COLUMNS)
            connection.execute(
                text(
                    "CREATE TABLE agent_audit_logs ("
                    + ", ".join(f"{name} TEXT" for name in sorted(columns))
                    + ")"
                )
            )
            prompt = "stored prompt" * 1000
            details = {
                column: f"{column}:\u4e2d\u6587\U0001f642"
                for column in migration.DETAIL_COLUMNS
            }
            records = [
                {"id": "existing", "request_messages": prompt},
                {"id": "unicode", **details},
                {"id": "empty", "response_content": ""},
                {"id": "null"},
            ]
            for record in records:
                connection.execute(
                    text(
                        "INSERT INTO agent_audit_logs ("
                        + ", ".join(record)
                        + ") VALUES ("
                        + ", ".join(f":{name}" for name in record)
                        + ")"
                    ),
                    record,
                )
            monkeypatch.setattr(
                migration, "op", Operations(MigrationContext.configure(connection))
            )
            if database == "postgresql":
                upgrade_dashboard_metadata_indexes(migration)
            else:
                migration.upgrade()
            expected_indexes = dict(migration.INDEXES)
            expected_indexes[migration.DETAIL_STORAGE_INDEX] = [
                "has_details",
                "detail_bytes",
            ]
            assert {
                i["name"]: i["column_names"]
                for i in inspect(connection).get_indexes("agent_audit_logs")
            } == expected_indexes
            assert connection.execute(
                text(
                    "SELECT has_details, detail_bytes FROM agent_audit_logs WHERE id = 'existing'"
                )
            ).one() == (1, len(prompt.encode("utf-8")))
            assert connection.execute(
                text(
                    "SELECT id, has_details, detail_bytes FROM agent_audit_logs ORDER BY id"
                )
            ).all() == [
                ("empty", True, 0),
                ("existing", True, len(prompt.encode("utf-8"))),
                ("null", False, 0),
                (
                    "unicode",
                    True,
                    sum(len(value.encode("utf-8")) for value in details.values()),
                ),
            ]
            assert {
                column["name"]: column["nullable"]
                for column in inspect(connection).get_columns("agent_audit_logs")
                if column["name"] in {"has_details", "detail_bytes"}
            } == {"has_details": False, "detail_bytes": False}
            connection.execute(text("INSERT INTO agent_audit_logs (id) VALUES ('new')"))
            assert connection.execute(
                text(
                    "SELECT has_details, detail_bytes FROM agent_audit_logs WHERE id = 'new'"
                )
            ).one() == (False, 0)
            model_indexes = {
                i.name: [c.name for c in i.columns]
                for i in LLMAuditLog.__table__.indexes
            }
            for name, names in expected_indexes.items():
                assert model_indexes[name] == names
            migration.downgrade()
            assert not inspect(connection).get_indexes("agent_audit_logs")
            assert connection.execute(
                text(
                    "SELECT id, request_messages FROM agent_audit_logs WHERE id = 'existing'"
                )
            ).one() == ("existing", "stored prompt" * 1000)
            assert not {"has_details", "detail_bytes"} & {
                column["name"]
                for column in inspect(connection).get_columns("agent_audit_logs")
            }
            transaction.rollback()
    finally:
        engine.dispose()
