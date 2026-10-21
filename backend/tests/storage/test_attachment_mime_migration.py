from importlib import import_module
from io import StringIO
import os
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, text

from app.agent_runtime.persistence.model import AgentAttachment


_LONG_MIME_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_SHORT_MIME_TYPE = "application/pdf"


def _load_migration():
    return import_module(
        "app.storage.migrations.versions.1029_expand_attachment_mime_type"
    )


def _run_migration_operation(connection, operation) -> None:
    migration_context = MigrationContext.configure(connection)
    with Operations.context(migration_context):
        operation()


def _create_attachment_table(connection, mime_length: int) -> None:
    connection.execute(
        text(
            "CREATE TABLE agent_attachments ("
            "id VARCHAR(21) PRIMARY KEY, "
            f"mime_type VARCHAR({mime_length}) NOT NULL, "
            "payload TEXT NOT NULL"
            ")"
        )
    )


def _mime_length(connection) -> int | None:
    column = next(
        column
        for column in inspect(connection).get_columns("agent_attachments")
        if column["name"] == "mime_type"
    )
    return column["type"].length


def test_agent_attachment_model_allows_standard_office_mime_types() -> None:
    assert AgentAttachment.__table__.c.mime_type.type.length == 255


def test_sqlite_upgrade_rebuilds_attachment_table_without_losing_mime_values() -> None:
    migration = _load_migration()
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            _create_attachment_table(connection, mime_length=50)
            connection.execute(
                text("INSERT INTO agent_attachments VALUES (:id, :mime_type, :payload)"),
                {
                    "id": "office-document",
                    "mime_type": _LONG_MIME_TYPE,
                    "payload": "preserve me",
                },
            )

            _run_migration_operation(connection, migration.upgrade)

            assert _mime_length(connection) == 255
            assert connection.execute(
                text("SELECT mime_type, payload FROM agent_attachments")
            ).one() == (_LONG_MIME_TYPE, "preserve me")
    finally:
        engine.dispose()


def test_sqlite_upgrade_is_idempotent_for_already_wide_attachment_column() -> None:
    migration = _load_migration()
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            _create_attachment_table(connection, mime_length=255)
            connection.execute(
                text("INSERT INTO agent_attachments VALUES (:id, :mime_type, :payload)"),
                {
                    "id": "office-document",
                    "mime_type": _LONG_MIME_TYPE,
                    "payload": "preserve me",
                },
            )

            _run_migration_operation(connection, migration.upgrade)

            assert _mime_length(connection) == 255
            assert connection.execute(
                text("SELECT mime_type FROM agent_attachments")
            ).scalar_one() == _LONG_MIME_TYPE
    finally:
        engine.dispose()


def test_sqlite_downgrade_rejects_mime_values_over_50_characters() -> None:
    migration = _load_migration()
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            _create_attachment_table(connection, mime_length=255)
            connection.execute(
                text("INSERT INTO agent_attachments VALUES (:id, :mime_type, :payload)"),
                {
                    "id": "office-document",
                    "mime_type": _LONG_MIME_TYPE,
                    "payload": "preserve me",
                },
            )

            with pytest.raises(RuntimeError, match="50"):
                _run_migration_operation(connection, migration.downgrade)

            assert _mime_length(connection) == 255
            assert connection.execute(
                text("SELECT mime_type FROM agent_attachments")
            ).scalar_one() == _LONG_MIME_TYPE
    finally:
        engine.dispose()


def test_postgresql_offline_migration_does_not_silently_truncate_on_downgrade() -> None:
    migration = _load_migration()

    upgrade_output = StringIO()
    upgrade_context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": upgrade_output},
    )
    with Operations.context(upgrade_context):
        migration.upgrade()

    downgrade_output = StringIO()
    downgrade_context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": downgrade_output},
    )
    with Operations.context(downgrade_context):
        migration.downgrade()

    assert "ALTER TABLE agent_attachments ALTER COLUMN mime_type TYPE VARCHAR(255)" in upgrade_output.getvalue()
    downgrade_sql = downgrade_output.getvalue()
    assert "ALTER TABLE agent_attachments ALTER COLUMN mime_type TYPE VARCHAR(50)" in downgrade_sql
    assert "USING left" not in downgrade_sql


def test_postgresql_existing_1028_attachment_table_upgrades_and_rejects_lossy_downgrade() -> None:
    database_url = os.getenv("OPENFIC_TEST_DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("Set OPENFIC_TEST_DATABASE_URL to test PostgreSQL")

    migration = _load_migration()
    engine = create_engine(database_url)
    schema = f"attachment_mime_{uuid4().hex}"
    try:
        with engine.connect() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.commit()
            connection.execute(text(f'SET search_path TO "{schema}"'))
            connection.commit()

            with connection.begin():
                _create_attachment_table(connection, mime_length=50)
                connection.execute(
                    text(
                        "INSERT INTO agent_attachments VALUES "
                        "('short', :mime_type, 'existing data')"
                    ),
                    {"mime_type": _SHORT_MIME_TYPE},
                )

                _run_migration_operation(connection, migration.upgrade)
                _run_migration_operation(connection, migration.upgrade)

                assert _mime_length(connection) == 255
                connection.execute(
                    text(
                        "INSERT INTO agent_attachments VALUES "
                        "('long', :mime_type, 'new data')"
                    ),
                    {"mime_type": _LONG_MIME_TYPE},
                )

                with pytest.raises(RuntimeError, match="50"):
                    _run_migration_operation(connection, migration.downgrade)

                assert _mime_length(connection) == 255
                assert connection.execute(
                    text("SELECT mime_type FROM agent_attachments WHERE id = 'long'")
                ).scalar_one() == _LONG_MIME_TYPE
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
