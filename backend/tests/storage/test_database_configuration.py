from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from app.settings import Settings
from app.storage.database import ALEMBIC_INI_PATH


@pytest.fixture
def settings_factory(monkeypatch):
    monkeypatch.delenv("OPENFIC_DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENFIC_CHECKPOINT_DATABASE_URL", raising=False)
    return lambda **kwargs: Settings(_env_file=None, **kwargs)


def test_sqlite_remains_default_and_empty_env_is_unset(settings_factory):
    settings = settings_factory(OPENFIC_DATABASE_URL="", OPENFIC_CHECKPOINT_DATABASE_URL=" ")
    assert settings.database_url.startswith("sqlite+aiosqlite:///")
    assert not settings.uses_postgresql
    assert not settings.uses_postgresql_checkpoints


@pytest.mark.parametrize("business,checkpoint", [(True, False), (False, True), (True, True)])
def test_database_backends_are_independently_selectable(settings_factory, business, checkpoint):
    settings = settings_factory(
        OPENFIC_DATABASE_URL="postgresql://user:p%40ss@localhost/app" if business else None,
        OPENFIC_CHECKPOINT_DATABASE_URL="postgresql://user:p%40ss@localhost/checkpoint" if checkpoint else None,
    )
    assert settings.uses_postgresql is business
    assert settings.uses_postgresql_checkpoints is checkpoint
    if business:
        assert settings.database_url.startswith("postgresql+psycopg://")
    assert "p%40ss" not in repr(settings)
    assert "database_url_override" not in settings.model_dump()
    assert "checkpoint_database_url" not in settings.model_dump()


@pytest.mark.parametrize("field,value", [
    ("OPENFIC_DATABASE_URL", "mysql://user:secret@localhost/app"),
    ("OPENFIC_DATABASE_URL", "postgresql+asyncpg://user:secret@localhost/app"),
    ("OPENFIC_CHECKPOINT_DATABASE_URL", "postgre://user:secret@localhost/app"),
    ("OPENFIC_CHECKPOINT_DATABASE_URL", "sqlite:///checkpoints.db"),
])
def test_invalid_database_config_fails_without_silent_fallback(settings_factory, field, value):
    with pytest.raises(ValidationError) as exc:
        settings_factory(**{field: value})
    assert "secret" not in str(exc.value)


@pytest.mark.parametrize("start", ["1021", "1022"])
def test_upgrade_upstream_sqlite_preserves_data_and_adds_pinyin(tmp_path: Path, start):
    config = Config(str(ALEMBIC_INI_PATH))
    database = tmp_path / "upgrade.db"
    config.attributes["database_url"] = f"sqlite:///{database}"
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())
    assert len({item.revision for item in revisions}) == len(revisions)
    assert len(script.get_heads()) == 1
    command.upgrade(config, start)
    engine = create_engine(f"sqlite:///{database}")
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO projects (id,title,word_count,chapter_count,created_at,updated_at) "
                              "VALUES ('existing','测试项目',0,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        command.upgrade(config, "head")
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT title_pinyin_full FROM projects")) == "ceshixiangmu"
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == script.get_current_head()
        columns = {col["name"]: col for col in inspect(engine).get_columns("agent_attachments")}
        assert {"content", "content_length", "line_count"} <= columns.keys()
        assert columns["width"]["nullable"]
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_failed_postgres_setup_closes_connection_and_can_retry(monkeypatch):
    from unittest.mock import AsyncMock
    from app.agent_runtime.runner import checkpointer

    conn = AsyncMock()
    saver = AsyncMock()
    saver.setup.side_effect = RuntimeError("setup failed")
    monkeypatch.setattr(checkpointer, "_checkpointer", None)
    monkeypatch.setattr(checkpointer.app_settings.settings, "checkpoint_database_url", "postgresql://localhost/test")
    monkeypatch.setattr(checkpointer, "_open_postgres_checkpoint_connection", AsyncMock(return_value=conn))
    monkeypatch.setattr(checkpointer, "AsyncPostgresSaver", lambda *args, **kwargs: saver)
    with pytest.raises(RuntimeError, match="setup failed"):
        await checkpointer.get_checkpointer()
    conn.close.assert_awaited_once()
    assert checkpointer._checkpointer is None
    saver.setup.side_effect = None
    assert await checkpointer.get_checkpointer() is saver
