import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app.storage.models.llm_audit_log import LLMAuditLog


def test_dashboard_metadata_indexes_migrate_existing_records(tmp_path, monkeypatch):
    migration = importlib.import_module(
        "app.storage.migrations.versions.1027_dashboard_metadata_indexes"
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    try:
        with engine.begin() as connection:
            columns = {name for _, names in migration.INDEXES for name in names}
            connection.execute(
                text(
                    "CREATE TABLE agent_audit_logs ("
                    + ", ".join(f"{name} TEXT" for name in sorted(columns))
                    + ", request_messages TEXT)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO agent_audit_logs (id, request_messages) VALUES ('existing', :prompt)"
                ),
                {"prompt": "stored prompt" * 1000},
            )
            monkeypatch.setattr(
                migration, "op", Operations(MigrationContext.configure(connection))
            )
            migration.upgrade()
            assert {
                i["name"]: i["column_names"]
                for i in inspect(connection).get_indexes("agent_audit_logs")
            } == dict(migration.INDEXES)
            model_indexes = {
                i.name: [c.name for c in i.columns]
                for i in LLMAuditLog.__table__.indexes
            }
            for name, names in migration.INDEXES:
                assert model_indexes[name] == names
            migration.downgrade()
            assert not inspect(connection).get_indexes("agent_audit_logs")
            assert connection.execute(
                text("SELECT id, request_messages FROM agent_audit_logs")
            ).one() == ("existing", "stored prompt" * 1000)
    finally:
        engine.dispose()
