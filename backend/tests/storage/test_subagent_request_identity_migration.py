from importlib import import_module

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


def test_notification_identity_upgrade_unique_scope_legacy_nulls_and_downgrade():
    migration = import_module(
        "app.storage.migrations.versions.1032_subagent_request_identity"
    )
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE agent_child_run_requests (id TEXT PRIMARY KEY, parent_session_id TEXT NOT NULL, content TEXT NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO agent_child_run_requests VALUES ('old', 'parent', 'preserved')"
                )
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            assert connection.execute(
                text(
                    "SELECT content, source_call FROM agent_child_run_requests WHERE id='old'"
                )
            ).one() == ("preserved", None)
            insert = text(
                "INSERT INTO agent_child_run_requests (id,parent_session_id,content,source_call) VALUES (:id,:parent,'text',:source)"
            )
            connection.execute(
                insert, {"id": "first", "parent": "parent", "source": "rev:tool"}
            )
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(
                    insert, {"id": "replay", "parent": "parent", "source": "rev:tool"}
                )
            connection.execute(
                insert, {"id": "other-parent", "parent": "other", "source": "rev:tool"}
            )
            connection.execute(
                insert, {"id": "legacy-2", "parent": "parent", "source": None}
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
            assert {
                column["name"]
                for column in inspect(connection).get_columns(
                    "agent_child_run_requests"
                )
            } == {"id", "parent_session_id", "content"}
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM agent_child_run_requests")
                ).scalar_one()
                == 4
            )
    finally:
        engine.dispose()
