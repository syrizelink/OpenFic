from __future__ import annotations

import aiosqlite
import pytest
from types import SimpleNamespace
from unittest.mock import Mock

import app.agent_runtime.runner.checkpointer as checkpointer_mod
from app.agent_runtime.runner.checkpointer import (
    checkpoint_free_page_bytes,
    full_vacuum_checkpoint_database,
    get_checkpointer,
    incremental_vacuum_checkpoint_database,
    migrate_checkpoint_database_to_incremental,
    needs_incremental_auto_vacuum_migration,
    reset_checkpointer,
    vacuum_checkpoint_database,
)
from app.main import _friendly_maintenance_error

pytestmark = pytest.mark.usefixtures("fast_checkpoint_sqlite")


@pytest.fixture(autouse=True)
def use_sqlite_checkpointer_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep SQLite maintenance tests independent from the host backend."""
    monkeypatch.setattr(checkpointer_mod.app_settings.settings, "database_backend", "sqlite")
    monkeypatch.setattr(checkpointer_mod.app_settings.settings, "checkpoint_database_url", None)


@pytest.mark.asyncio
async def test_new_checkpoint_database_uses_incremental_auto_vacuum(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    db_path = tmp_path / "checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()

    try:
        checkpointer = await get_checkpointer()
        cursor = await checkpointer.conn.execute("PRAGMA auto_vacuum")
        try:
            row = await cursor.fetchone()
        finally:
            await cursor.close()
        assert row == (2,)
    finally:
        await reset_checkpointer()


@pytest.mark.asyncio
async def test_existing_checkpoint_database_is_migrated_to_incremental(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    db_path = tmp_path / "checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    conn = await aiosqlite.connect(db_path)
    try:
        await conn.execute("CREATE TABLE test_data (value BLOB)")
        await conn.execute("INSERT INTO test_data(value) VALUES (zeroblob(8192))")
        await conn.commit()
    finally:
        await conn.close()

    phases: list[str] = []
    assert await migrate_checkpoint_database_to_incremental(
        progress_callback=lambda phase, *_: phases.append(phase),
    )

    conn = await aiosqlite.connect(db_path)
    try:
        cursor = await conn.execute("PRAGMA auto_vacuum")
        try:
            row = await cursor.fetchone()
        finally:
            await cursor.close()
    finally:
        await conn.close()

    assert row == (2,)
    assert phases and set(phases) == {"migrating"}


@pytest.mark.asyncio
async def test_incremental_vacuum_reclaims_free_pages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    db_path = tmp_path / "checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()
    checkpointer = await get_checkpointer()
    try:
        await checkpointer.conn.execute("CREATE TABLE test_data (value BLOB)")
        await checkpointer.conn.execute(
            "INSERT INTO test_data(value) VALUES (zeroblob(32768))"
        )
        await checkpointer.conn.execute("DELETE FROM test_data")
        await checkpointer.conn.commit()
    finally:
        await reset_checkpointer()

    phases: list[str] = []
    assert await incremental_vacuum_checkpoint_database(
        min_free_bytes=1,
        batch_bytes=16384,
        progress_callback=lambda phase, *_: phases.append(phase),
    )
    assert phases
    assert set(phases) == {"vacuuming"}


@pytest.mark.asyncio
async def test_postgresql_checkpoint_maintenance_does_not_access_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        checkpointer_mod.app_settings,
        "settings",
        SimpleNamespace(database_backend="postgresql"),
    )
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(tmp_path / "legacy.db"))
    monkeypatch.setattr(
        checkpointer_mod,
        "_get_db_path",
        Mock(side_effect=AssertionError("SQLite path must not be read")),
    )
    monkeypatch.setattr(
        checkpointer_mod.aiosqlite,
        "connect",
        Mock(side_effect=AssertionError("SQLite must not be accessed")),
    )

    assert await needs_incremental_auto_vacuum_migration() is False
    assert await checkpoint_free_page_bytes() == (0, 0)
    assert await migrate_checkpoint_database_to_incremental() is False
    assert await full_vacuum_checkpoint_database() is False
    assert await incremental_vacuum_checkpoint_database() is False
    assert await vacuum_checkpoint_database() is False


def test_friendly_maintenance_error_maps_disk_full() -> None:
    message = _friendly_maintenance_error(RuntimeError("database or disk is full"))
    assert "磁盘空间不足" in message


def test_friendly_maintenance_error_keeps_other_errors() -> None:
    message = _friendly_maintenance_error(RuntimeError("boom"))
    assert "boom" in message
