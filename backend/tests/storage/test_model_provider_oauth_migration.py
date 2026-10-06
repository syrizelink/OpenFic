import importlib
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


def test_provider_oauth_migration_round_trip(tmp_path, monkeypatch):
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config()
    config.set_main_option("script_location", str(backend_dir / "app/storage/migrations"))
    assert ScriptDirectory.from_config(config).get_current_head() == "1025"
    migration = importlib.import_module("app.storage.migrations.versions.1025_add_model_provider_oauth")
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE model_providers (id TEXT PRIMARY KEY, name TEXT NOT NULL, api_key_encrypted TEXT NOT NULL)"))
            connection.execute(text("INSERT INTO model_providers VALUES ('existing', 'Existing', 'encrypted-api-key')"))
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            table = "model_provider_oauth_registrations"
            assert set(inspect(connection).get_pk_constraint(table)["constrained_columns"]) == {
                "provider_type", "issuer", "client_id"
            }
            for provider_type, issuer in [
                ("one", "https://first.example"),
                ("two", "https://first.example"),
                ("one", "https://second.example"),
            ]:
                connection.execute(
                    text(
                        f"INSERT INTO {table} (provider_type, issuer, client_id) "
                        "VALUES (:provider_type, :issuer, 'same-client')"
                    ),
                    {"provider_type": provider_type, "issuer": issuer},
                )
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(
                    text(
                        f"INSERT INTO {table} (provider_type, issuer, client_id) "
                        "VALUES ('one', 'https://first.example', 'same-client')"
                    )
                )
            connection.execute(text("UPDATE model_providers SET credentials_encrypted = 'encrypted-oauth-tokens'"))
            migration.downgrade()
            assert table not in inspect(connection).get_table_names()
            assert "credentials_encrypted" not in {
                column["name"] for column in inspect(connection).get_columns("model_providers")
            }
            assert connection.execute(
                text("SELECT id, name, api_key_encrypted FROM model_providers")
            ).one() == ("existing", "Existing", "encrypted-api-key")
            migration.upgrade()
            assert connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() == 0
            assert connection.execute(text("SELECT credentials_encrypted FROM model_providers")).scalar_one() == ""
    finally:
        engine.dispose()
