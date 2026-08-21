from __future__ import annotations

import aiosqlite
import pytest

from app.agent_runtime.runner.checkpointer import (
    get_checkpointer,
    incremental_vacuum_checkpoint_database,
    migrate_checkpoint_database_to_incremental,
    reset_checkpointer,
)
from app.main import _friendly_maintenance_error

pytestmark = pytest.mark.usefixtures("fast_checkpoint_sqlite")


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


def test_friendly_maintenance_error_maps_disk_full() -> None:
    message = _friendly_maintenance_error(RuntimeError("database or disk is full"))
    assert "磁盘空间不足" in message


def test_friendly_maintenance_error_keeps_other_errors() -> None:
    message = _friendly_maintenance_error(RuntimeError("boom"))
    assert "boom" in message
