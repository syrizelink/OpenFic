import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.settings import BACKEND_DATA_DIR, Settings
import app.storage.database as database
from app.storage.models.commit import Commit


def test_settings_default_to_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENFIC_DATABASE_BACKEND", raising=False)
    monkeypatch.delenv("OPENFIC_DATABASE_URL", raising=False)
    monkeypatch.delenv("OPENFIC_CHECKPOINT_DATABASE_URL", raising=False)

    app_settings = Settings(_env_file=None)

    assert app_settings.database_backend == "sqlite"
    assert (
        app_settings.database_url
        == f"sqlite+aiosqlite:///{BACKEND_DATA_DIR}/openfic.db"
    )
    assert app_settings.database_sync_url == f"sqlite:///{BACKEND_DATA_DIR}/openfic.db"


def test_settings_select_postgresql_url(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "postgresql+psycopg://user:password@localhost/openfic"
    monkeypatch.setenv("OPENFIC_DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv("OPENFIC_DATABASE_URL", database_url)
    monkeypatch.setenv(
        "OPENFIC_CHECKPOINT_DATABASE_URL",
        "postgresql://user:password@localhost/openfic_checkpoints",
    )

    app_settings = Settings(_env_file=None)

    assert app_settings.database_backend == "postgresql"
    assert app_settings.database_url == database_url
    assert app_settings.database_sync_url == database_url


def test_settings_expose_independent_checkpoint_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = "postgresql+psycopg://user:password@localhost/openfic"
    checkpoint_database_url = "postgresql://user:password@localhost/openfic_checkpoints"
    monkeypatch.setenv("OPENFIC_DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv("OPENFIC_DATABASE_URL", database_url)
    monkeypatch.setenv(
        "OPENFIC_CHECKPOINT_DATABASE_URL",
        checkpoint_database_url,
    )

    app_settings = Settings(_env_file=None)

    assert app_settings.checkpoint_database_url == checkpoint_database_url


def test_settings_accept_postgres_dsn_alias_for_checkpoint_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENFIC_DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv(
        "OPENFIC_DATABASE_URL",
        "postgresql+psycopg://user:password@localhost/openfic",
    )
    checkpoint_database_url = "postgres://user:password@localhost/openfic_checkpoints"
    monkeypatch.setenv(
        "OPENFIC_CHECKPOINT_DATABASE_URL",
        checkpoint_database_url,
    )

    app_settings = Settings(_env_file=None)

    assert app_settings.checkpoint_database_url == checkpoint_database_url


def test_postgresql_settings_require_explicit_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENFIC_DATABASE_BACKEND", "postgresql")
    monkeypatch.delenv("OPENFIC_DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="OPENFIC_DATABASE_URL"):
        Settings(_env_file=None)


def test_postgresql_settings_do_not_require_checkpoint_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENFIC_DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv(
        "OPENFIC_DATABASE_URL",
        "postgresql+psycopg://user:password@localhost/openfic",
    )
    monkeypatch.delenv("OPENFIC_CHECKPOINT_DATABASE_URL", raising=False)

    app_settings = Settings(_env_file=None)

    assert app_settings.database_backend == "postgresql"
    assert app_settings.checkpoint_database_url is None


def test_commit_chapter_reference_is_historical_not_a_live_foreign_key() -> None:
    assert not any(
        tuple(constraint.column_keys) == ("chapter_id",)
        and constraint.referred_table.name == "chapters"
        for constraint in Commit.__table__.foreign_key_constraints
    )


def test_sqlite_settings_reject_postgresql_checkpoint_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENFIC_DATABASE_BACKEND", "sqlite")
    monkeypatch.delenv("OPENFIC_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "OPENFIC_CHECKPOINT_DATABASE_URL",
        "postgresql://user:password@localhost/openfic_checkpoints",
    )

    with pytest.raises(ValueError, match="only supported"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("backend", "database_url"),
    [
        ("sqlite", "postgresql+psycopg://user:password@localhost/openfic"),
        ("sqlite", "postgresql://user:password@localhost/openfic"),
        ("sqlite", "postgresql+asyncpg://user:password@localhost/openfic"),
        ("postgresql", "sqlite+aiosqlite:////tmp/openfic.db"),
        ("postgresql", "sqlite:////tmp/openfic.db"),
        ("sqlite", "sqlite:////tmp/openfic.db"),
        ("postgresql", "postgresql://user:password@localhost/openfic"),
        ("postgresql", "postgresql+asyncpg://user:password@localhost/openfic"),
        ("postgresql", "not-a-database-url"),
    ],
)
def test_settings_reject_mismatched_or_unsupported_database_urls(
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
    database_url: str,
) -> None:
    monkeypatch.setenv("OPENFIC_DATABASE_BACKEND", backend)
    monkeypatch.setenv("OPENFIC_DATABASE_URL", database_url)
    if backend == "postgresql":
        monkeypatch.setenv(
            "OPENFIC_CHECKPOINT_DATABASE_URL",
            "postgresql://user:password@localhost/openfic_checkpoints",
        )
    else:
        monkeypatch.delenv("OPENFIC_CHECKPOINT_DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="OPENFIC_DATABASE_URL"):
        Settings(_env_file=None)


@pytest.mark.parametrize("backend", ["mysql", "sqlite3", ""])
def test_settings_reject_unsupported_database_backends(
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
) -> None:
    monkeypatch.setenv("OPENFIC_DATABASE_BACKEND", backend)
    monkeypatch.delenv("OPENFIC_DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="OPENFIC_DATABASE_BACKEND"):
        Settings(_env_file=None)


def _prepare_engine_test(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock, Mock]:
    fake_engine = Mock()
    fake_engine.sync_engine = object()
    create_engine = Mock(return_value=fake_engine)
    listen = Mock()
    monkeypatch.setattr(database, "create_async_engine", create_engine)
    monkeypatch.setattr(database.event, "listen", listen)
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_async_session_factory", None)
    return fake_engine, create_engine, listen


def test_sqlite_engine_keeps_connect_args_and_sqlite_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine, create_engine, listen = _prepare_engine_test(monkeypatch)
    monkeypatch.setattr(
        database,
        "settings",
        SimpleNamespace(
            database_backend="sqlite",
            database_url="sqlite+aiosqlite:////tmp/openfic.db",
            debug=False,
        ),
    )

    assert database._get_engine() is fake_engine

    assert create_engine.call_args.args == ("sqlite+aiosqlite:////tmp/openfic.db",)
    assert create_engine.call_args.kwargs["connect_args"] == {
        "check_same_thread": False,
    }
    listen.assert_called_once_with(
        fake_engine.sync_engine, "connect", database._set_sqlite_pragma
    )


def test_postgresql_engine_does_not_run_sqlite_connect_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine, create_engine, listen = _prepare_engine_test(monkeypatch)
    monkeypatch.setattr(
        database,
        "settings",
        SimpleNamespace(
            database_backend="postgresql",
            database_url="postgresql+psycopg://user:password@localhost/openfic",
            debug=False,
        ),
    )

    assert database._get_engine() is fake_engine

    assert "connect_args" not in create_engine.call_args.kwargs
    listen.assert_called_once_with(
        fake_engine.sync_engine,
        "connect",
        database._set_postgresql_timezone,
    )


@pytest.mark.asyncio
async def test_init_db_runs_sync_upgrade_in_a_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upgrade = Mock()
    to_thread = AsyncMock()
    monkeypatch.setattr(database, "_upgrade_db_to_head", upgrade)
    monkeypatch.setattr(asyncio, "to_thread", to_thread)

    await database.init_db()

    to_thread.assert_awaited_once_with(upgrade)
    upgrade.assert_not_called()
