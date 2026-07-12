import os
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import app.agent_runtime.runner.checkpointer as checkpointer_mod
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import pytest
from app.agent_runtime.runner.checkpointer import (
    close_checkpointer,
    delete_checkpoints_after_for_thread,
    delete_checkpoints_for_thread,
    get_checkpointer,
    init_checkpointer,
    reset_checkpointer,
)


@pytest.mark.asyncio
async def test_get_checkpointer_removes_api_keys_from_legacy_checkpoints():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_checkpoints.db")
        os.environ["AGENT_CHECKPOINT_DB"] = db_path
        await reset_checkpointer()

        conn = await aiosqlite.connect(db_path)
        legacy_checkpointer = AsyncSqliteSaver(conn)
        await legacy_checkpointer.setup()
        config = {
            "configurable": {
                "thread_id": "legacy-session",
                "checkpoint_ns": "",
            }
        }
        checkpoint = {
            "v": 2,
            "id": "legacy-checkpoint",
            "ts": "2026-07-12T00:00:00+00:00",
            "channel_values": {
                "model_config": {
                    "model_record_id": "model-1",
                    "model_id": "gpt-test",
                    "api_key": "legacy-secret",
                }
            },
            "channel_versions": {},
            "versions_seen": {},
            "pending_sends": [],
        }
        await legacy_checkpointer.aput(config, checkpoint, {}, {})
        await conn.close()

        checkpointer = await get_checkpointer()
        persisted = await checkpointer.aget_tuple(config)

        assert persisted is not None
        assert "api_key" not in persisted.checkpoint["channel_values"]["model_config"]

        del os.environ["AGENT_CHECKPOINT_DB"]
        await reset_checkpointer()


async def test_get_checkpointer_creates_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_checkpoints.db")
        os.environ["AGENT_CHECKPOINT_DB"] = db_path
        await reset_checkpointer()

        checkpointer = await get_checkpointer()
        assert checkpointer is not None
        assert os.path.exists(db_path)

        # Cleanup
        del os.environ["AGENT_CHECKPOINT_DB"]
        await reset_checkpointer()


async def test_get_checkpointer_uses_backend_data_default_path(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        backend_dir = repo_root / "backend"
        data_dir = backend_dir / "data"

        monkeypatch.delenv("AGENT_CHECKPOINT_DB", raising=False)
        monkeypatch.setattr(checkpointer_mod.app_settings, "BACKEND_DIR", backend_dir)
        monkeypatch.setattr(checkpointer_mod.app_settings, "BACKEND_DATA_DIR", data_dir)
        await reset_checkpointer()

        await get_checkpointer()

        assert (data_dir / "checkpoints.db").exists()

        await reset_checkpointer()


async def test_get_checkpointer_migrates_legacy_db_and_removes_old_backend_file(
    monkeypatch,
):
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        backend_dir = repo_root / "backend"
        data_dir = backend_dir / "data"
        legacy_root_dir = repo_root / "data" / "agent"
        legacy_root_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)

        legacy_runtime_path = legacy_root_dir / "langgraph_checkpoints.db"
        sqlite3.connect(legacy_runtime_path).execute("CREATE TABLE marker (id INTEGER)")
        sqlite3.connect(legacy_runtime_path).close()

        legacy_backend_path = data_dir / "agent_checkpoints.db"
        sqlite3.connect(legacy_backend_path).execute("CREATE TABLE stale (id INTEGER)")
        sqlite3.connect(legacy_backend_path).close()

        monkeypatch.delenv("AGENT_CHECKPOINT_DB", raising=False)
        monkeypatch.setattr(checkpointer_mod.app_settings, "BACKEND_DIR", backend_dir)
        monkeypatch.setattr(checkpointer_mod.app_settings, "BACKEND_DATA_DIR", data_dir)
        await reset_checkpointer()

        await get_checkpointer()

        target_path = data_dir / "checkpoints.db"
        assert target_path.exists()
        assert not legacy_runtime_path.exists()
        assert not legacy_backend_path.exists()

        with sqlite3.connect(target_path) as conn:
            assert conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'marker'"
            ).fetchone() == ("marker",)

        await reset_checkpointer()


async def test_init_checkpointer_preinitializes_and_close_releases_connection():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_checkpoints.db")
        os.environ["AGENT_CHECKPOINT_DB"] = db_path
        await reset_checkpointer()

        checkpointer = await init_checkpointer()
        assert checkpointer is await get_checkpointer()
        assert os.path.exists(db_path)

        await close_checkpointer()
        assert checkpointer_mod._checkpointer is None

        del os.environ["AGENT_CHECKPOINT_DB"]


async def test_delete_checkpoints_for_thread_removes_matching_rows_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_checkpoints.db")
        os.environ["AGENT_CHECKPOINT_DB"] = db_path
        await reset_checkpointer()
        await get_checkpointer()

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id) VALUES (?, ?, ?)",
                ("session-a", "", "cp-a"),
            )
            conn.execute(
                "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id) VALUES (?, ?, ?)",
                ("session-b", "", "cp-b"),
            )
            conn.execute(
                "INSERT INTO writes(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel) VALUES (?, ?, ?, ?, ?, ?)",
                ("session-a", "", "cp-a", "task-a", 0, "messages"),
            )
            conn.execute(
                "INSERT INTO writes(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel) VALUES (?, ?, ?, ?, ?, ?)",
                ("session-b", "", "cp-b", "task-b", 0, "messages"),
            )
            conn.commit()

        deleted_rows = await delete_checkpoints_for_thread("session-a")

        assert deleted_rows == 2
        with sqlite3.connect(db_path) as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?",
                ("session-a",),
            ).fetchone() == (0,)
            assert conn.execute(
                "SELECT COUNT(*) FROM writes WHERE thread_id = ?",
                ("session-a",),
            ).fetchone() == (0,)
            assert conn.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?",
                ("session-b",),
            ).fetchone() == (1,)
            assert conn.execute(
                "SELECT COUNT(*) FROM writes WHERE thread_id = ?",
                ("session-b",),
            ).fetchone() == (1,)

        del os.environ["AGENT_CHECKPOINT_DB"]
        await reset_checkpointer()


async def test_delete_checkpoints_after_for_thread_keeps_cutoff_and_clears_subgraphs():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_checkpoints.db")
        os.environ["AGENT_CHECKPOINT_DB"] = db_path
        await reset_checkpointer()
        await get_checkpointer()

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id) VALUES (?, ?, ?)",
                ("session-a", "", "cp-001"),
            )
            conn.execute(
                "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id) VALUES (?, ?, ?)",
                ("session-a", "", "cp-002"),
            )
            conn.execute(
                "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id) VALUES (?, ?, ?)",
                ("session-a", "writer:abc", "cp-003"),
            )
            conn.execute(
                "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id) VALUES (?, ?, ?)",
                ("session-b", "", "cp-002"),
            )
            for cp_id, ns in [("cp-001", ""), ("cp-002", ""), ("cp-003", "writer:abc")]:
                conn.execute(
                    "INSERT INTO writes(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel) VALUES (?, ?, ?, ?, ?, ?)",
                    ("session-a", ns, cp_id, "task", 0, "messages"),
                )
            conn.execute(
                "INSERT INTO writes(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel) VALUES (?, ?, ?, ?, ?, ?)",
                ("session-b", "", "cp-002", "task", 0, "messages"),
            )
            conn.commit()

        deleted_rows = await delete_checkpoints_after_for_thread("session-a", "cp-001")

        assert deleted_rows == 4
        with sqlite3.connect(db_path) as conn:
            remaining = conn.execute(
                "SELECT checkpoint_ns, checkpoint_id FROM checkpoints WHERE thread_id = ? ORDER BY checkpoint_id",
                ("session-a",),
            ).fetchall()
            assert remaining == [("", "cp-001")]
            assert conn.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?",
                ("session-b",),
            ).fetchone() == (1,)
            assert conn.execute(
                "SELECT COUNT(*) FROM writes WHERE thread_id = ?",
                ("session-b",),
            ).fetchone() == (1,)

        del os.environ["AGENT_CHECKPOINT_DB"]
        await reset_checkpointer()


async def test_delete_checkpoints_after_for_thread_noops_on_empty_args():
    assert await delete_checkpoints_after_for_thread("", "cp-001") == 0
    assert await delete_checkpoints_after_for_thread("session-a", "") == 0


async def test_reset_checkpointer_closes_existing_connection(monkeypatch):
    close = AsyncMock()
    monkeypatch.setattr(
        checkpointer_mod,
        "_checkpointer",
        SimpleNamespace(conn=SimpleNamespace(close=close)),
    )

    await reset_checkpointer()

    close.assert_awaited_once()
    assert checkpointer_mod._checkpointer is None
