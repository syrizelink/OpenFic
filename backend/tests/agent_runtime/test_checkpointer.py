from contextlib import closing
import os
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import app.agent_runtime.runner.checkpointer as checkpointer_mod
import aiosqlite
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import pytest
from sqlalchemy import select
from app.agent_runtime.runner.checkpointer import (
    cleanup_unreachable_checkpoints,
    close_checkpointer,
    delete_checkpoints_after_for_thread,
    delete_checkpoints_for_thread,
    get_checkpointer,
    init_checkpointer,
    prune_checkpoints_for_thread,
    prune_reachable_checkpoints,
    reset_checkpointer,
    vacuum_checkpoint_database,
)
from app.agent_runtime.tools.impls.interaction.ask_user import Question, QuestionOption
from app.agent_runtime.persistence.child_runs import create_child_run
from app.agent_runtime.persistence.model import AgentChildRunRequest
from app.storage.models.revision import Revision
from app.storage.models.task import Task

pytestmark = pytest.mark.usefixtures("fast_checkpoint_sqlite")


@pytest.mark.asyncio
async def test_get_checkpointer_restores_legacy_question_checkpoint(
    monkeypatch, tmp_path
):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()

    try:
        conn = await aiosqlite.connect(db_path)
        legacy_checkpointer = AsyncSqliteSaver(conn)
        await legacy_checkpointer.setup()
        config = cast(
            RunnableConfig,
            {
                "configurable": {
                    "thread_id": "legacy-question-session",
                    "checkpoint_ns": "",
                }
            },
        )
        checkpoint = cast(
            Checkpoint,
            {
                "v": 2,
                "id": "legacy-question-checkpoint",
                "ts": "2026-07-12T00:00:00+00:00",
                "channel_values": {
                    "pending_question": Question(
                        title="继续方式",
                        description="请选择后续处理方式。",
                        options=[
                            QuestionOption(label="继续", description="继续执行"),
                            QuestionOption(label="暂停", description="暂停执行"),
                        ],
                    )
                },
                "channel_versions": {},
                "versions_seen": {},
                "pending_sends": [],
            },
        )
        await legacy_checkpointer.aput(config, checkpoint, {}, {})
        await conn.close()

        checkpointer = await get_checkpointer()
        persisted = await checkpointer.aget_tuple(config)

        assert persisted is not None
        question = persisted.checkpoint["channel_values"]["pending_question"]
        assert isinstance(question, Question)
        assert question.title == "继续方式"
        assert isinstance(question.options[0], QuestionOption)
    finally:
        await reset_checkpointer()


@pytest.mark.asyncio
async def test_get_checkpointer_removes_api_keys_from_legacy_checkpoints(
    monkeypatch: pytest.MonkeyPatch,
):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_checkpoints.db")
        os.environ["AGENT_CHECKPOINT_DB"] = db_path
        await reset_checkpointer()

        conn = await aiosqlite.connect(db_path)
        legacy_checkpointer = AsyncSqliteSaver(conn)
        await legacy_checkpointer.setup()
        config = cast(
            RunnableConfig,
            {
                "configurable": {
                    "thread_id": "legacy-session",
                    "checkpoint_ns": "",
                }
            },
        )
        checkpoint = cast(
            Checkpoint,
            {
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
            },
        )
        await legacy_checkpointer.aput(config, checkpoint, {}, {})
        await conn.close()

        async def fail_full_checkpoint_scan(*args, **kwargs):
            raise AssertionError("full checkpoint scan should not run")
            yield

        monkeypatch.setattr(AsyncSqliteSaver, "alist", fail_full_checkpoint_scan)
        checkpointer = await get_checkpointer()
        persisted = await checkpointer.aget_tuple(config)

        assert persisted is not None
        assert "api_key" not in persisted.checkpoint["channel_values"]["model_config"]

        del os.environ["AGENT_CHECKPOINT_DB"]
        await reset_checkpointer()


@pytest.mark.asyncio
async def test_get_checkpointer_runs_legacy_api_key_migration_once(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()

    try:
        await get_checkpointer()
        await reset_checkpointer()
        list_legacy_configs = AsyncMock()
        monkeypatch.setattr(
            checkpointer_mod,
            "_list_legacy_api_key_checkpoint_configs",
            list_legacy_configs,
        )

        await get_checkpointer()

        list_legacy_configs.assert_not_awaited()
    finally:
        await reset_checkpointer()


@pytest.mark.asyncio
async def test_get_checkpointer_does_not_scan_all_checkpoints_without_legacy_api_keys(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()

    async def fail_full_checkpoint_scan(*args, **kwargs):
        raise AssertionError("full checkpoint scan should not run")
        yield

    monkeypatch.setattr(AsyncSqliteSaver, "alist", fail_full_checkpoint_scan)

    try:
        checkpointer = await get_checkpointer()

        assert checkpointer is not None
    finally:
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


async def test_get_checkpointer_configures_concurrent_sqlite_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()

    try:
        checkpointer = await get_checkpointer()
        values: dict[str, object] = {}
        for pragma in ("journal_mode", "synchronous", "busy_timeout"):
            cursor = await checkpointer.conn.execute(f"PRAGMA {pragma}")
            try:
                row = await cursor.fetchone()
            finally:
                await cursor.close()
            values[pragma] = row[0] if row else None

        assert values == {
            "journal_mode": "wal",
            "synchronous": 1,
            "busy_timeout": 30000,
        }
    finally:
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
        with closing(sqlite3.connect(legacy_runtime_path)) as conn:
            conn.execute("CREATE TABLE marker (id INTEGER)")
            conn.commit()

        legacy_backend_path = data_dir / "agent_checkpoints.db"
        with closing(sqlite3.connect(legacy_backend_path)) as conn:
            conn.execute("CREATE TABLE stale (id INTEGER)")
            conn.commit()

        monkeypatch.delenv("AGENT_CHECKPOINT_DB", raising=False)
        monkeypatch.setattr(checkpointer_mod.app_settings, "BACKEND_DIR", backend_dir)
        monkeypatch.setattr(checkpointer_mod.app_settings, "BACKEND_DATA_DIR", data_dir)
        await reset_checkpointer()

        await get_checkpointer()

        target_path = data_dir / "checkpoints.db"
        assert target_path.exists()
        assert not legacy_runtime_path.exists()
        assert not legacy_backend_path.exists()

        with closing(sqlite3.connect(target_path)) as conn:
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

        with closing(sqlite3.connect(db_path)) as conn:
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
        with closing(sqlite3.connect(db_path)) as conn:
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

        with closing(sqlite3.connect(db_path)) as conn:
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
        with closing(sqlite3.connect(db_path)) as conn:
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


async def test_cleanup_unreachable_checkpoints_preserves_reachable_session_tree(
    client,
    session,
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()
    parent_session_id = "agent-root"
    task = Task(
        id="task-root",
        project_id="project-root",
        title="Root session",
        mode="agent",
        agent_session_id=parent_session_id,
    )
    session.add(task)
    await session.commit()
    child = await create_child_run(
        session,
        parent_session_id=parent_session_id,
        parent_task_id=task.id,
        parent_thread_id=parent_session_id,
        child_thread_id="agent-root:child:completed",
        agent_key="writer",
        dispatch_id="completed",
        tool_call_id="tool-completed",
        request={"task": "write", "input": {}, "metadata": {}},
        status="completed",
    )
    nested_child = await create_child_run(
        session,
        parent_session_id=child.child_thread_id,
        parent_task_id=task.id,
        parent_thread_id=child.child_thread_id,
        child_thread_id="agent-root:child:completed:child:nested",
        agent_key="reviewer",
        dispatch_id="nested",
        tool_call_id="tool-nested",
        request={"task": "review", "input": {}, "metadata": {}},
        status="completed",
    )
    await create_child_run(
        session,
        parent_session_id="deleted-agent-root",
        parent_task_id="deleted-task",
        parent_thread_id="deleted-agent-root",
        child_thread_id="deleted-agent-root:child:orphan",
        agent_key="writer",
        dispatch_id="orphan",
        tool_call_id="tool-orphan",
        request={"task": "write", "input": {}, "metadata": {}},
        status="completed",
    )

    checkpointer = await get_checkpointer()
    reachable_thread_ids = {
        parent_session_id,
        child.child_thread_id,
        nested_child.child_thread_id,
    }
    orphan_thread_ids = {
        "deleted-agent-root",
        "deleted-agent-root:child:orphan",
        "unrelated-thread",
    }
    for index, thread_id in enumerate([*reachable_thread_ids, *orphan_thread_ids]):
        checkpoint_id = f"checkpoint-{index}"
        await checkpointer.conn.execute(
            "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id) VALUES (?, ?, ?)",
            (thread_id, "", checkpoint_id),
        )
        await checkpointer.conn.execute(
            "INSERT INTO writes(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel) VALUES (?, ?, ?, ?, ?, ?)",
            (thread_id, "", checkpoint_id, "task", 0, "messages"),
        )
    await checkpointer.conn.commit()

    deleted_rows = await cleanup_unreachable_checkpoints(session, checkpointer)

    assert deleted_rows == 6
    cursor = await checkpointer.conn.execute(
        "SELECT thread_id FROM checkpoints UNION SELECT thread_id FROM writes"
    )
    try:
        remaining_thread_ids = {row[0] for row in await cursor.fetchall()}
    finally:
        await cursor.close()
    assert remaining_thread_ids == reachable_thread_ids
    await reset_checkpointer()


async def test_cleanup_unreachable_checkpoints_noops_for_empty_checkpoint_store(
    client,
    session,
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()

    try:
        assert (
            await cleanup_unreachable_checkpoints(session, await get_checkpointer())
            == 0
        )
    finally:
        await reset_checkpointer()


async def test_prune_checkpoints_for_thread_keeps_latest_and_rollback_boundaries(
    client,
    session,
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()
    task = Task(
        id="task-root",
        project_id="project-root",
        title="Root session",
        mode="agent",
        agent_session_id="agent-root",
    )
    session.add(task)
    await session.commit()

    checkpointer = await get_checkpointer()
    rows = [
        ("", "cp-001", None),
        ("", "cp-002", "cp-001"),
        ("", "cp-003", "cp-002"),
        ("primary:child", "cp-004", None),
        ("primary:child", "cp-005", "cp-004"),
    ]
    for namespace, checkpoint_id, parent_checkpoint_id in rows:
        await checkpointer.conn.execute(
            "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id) "
            "VALUES (?, ?, ?, ?)",
            ("agent-root", namespace, checkpoint_id, parent_checkpoint_id),
        )
        await checkpointer.conn.execute(
            "INSERT INTO writes(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("agent-root", namespace, checkpoint_id, "task", 0, "messages"),
        )
    await checkpointer.conn.commit()

    deleted_rows = await prune_checkpoints_for_thread(
        checkpointer,
        "agent-root",
        {"cp-002"},
    )

    assert deleted_rows == 4
    cursor = await checkpointer.conn.execute(
        "SELECT checkpoint_ns, checkpoint_id FROM checkpoints "
        "WHERE thread_id = ? ORDER BY checkpoint_id",
        ("agent-root",),
    )
    try:
        assert await cursor.fetchall() == [
            ("", "cp-002"),
            ("", "cp-003"),
            ("primary:child", "cp-005"),
        ]
    finally:
        await cursor.close()
    cursor = await checkpointer.conn.execute(
        "SELECT checkpoint_ns, checkpoint_id FROM writes "
        "WHERE thread_id = ? ORDER BY checkpoint_id",
        ("agent-root",),
    )
    try:
        assert await cursor.fetchall() == [
            ("", "cp-002"),
            ("", "cp-003"),
            ("primary:child", "cp-005"),
        ]
    finally:
        await cursor.close()
    await reset_checkpointer()


async def test_prune_reachable_checkpoints_keeps_revision_and_child_boundaries(
    client,
    session,
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()
    task = Task(
        id="task-root",
        project_id="project-root",
        title="Root session",
        mode="agent",
        agent_session_id="agent-root",
    )
    session.add(task)
    revision = Revision(
        id="revision-root",
        project_id=task.project_id,
        task_id=task.id,
        message="root boundary",
        agent_session_id="agent-root",
        status="completed",
        revision_type="agent",
        pre_run_checkpoint_id="root-002",
        graph_thread_id="agent-root",
        is_checkpoint=True,
        project_snapshot_title="Root session",
    )
    session.add(revision)
    await session.commit()
    child = await create_child_run(
        session,
        parent_session_id="agent-root",
        parent_task_id=task.id,
        parent_thread_id="agent-root",
        child_thread_id="agent-root:child:writer",
        agent_key="writer",
        dispatch_id="writer",
        tool_call_id="tool-writer",
        request={"task": "write", "input": {}, "metadata": {}},
    )
    request_result = await session.execute(
        select(AgentChildRunRequest).where(
            AgentChildRunRequest.child_run_id == child.id
        )
    )
    child_request = request_result.scalar_one()
    child_request.pre_request_checkpoint_id = "child-002"
    await session.commit()

    checkpointer = await get_checkpointer()
    for thread_id, checkpoint_ids in {
        "agent-root": ("root-001", "root-002", "root-003"),
        child.child_thread_id: ("child-001", "child-002", "child-003"),
    }.items():
        for checkpoint_id in checkpoint_ids:
            await checkpointer.conn.execute(
                "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id) VALUES (?, ?, ?)",
                (thread_id, "", checkpoint_id),
            )
    await checkpointer.conn.commit()

    deleted_rows = await prune_reachable_checkpoints(session, checkpointer)

    assert deleted_rows == 2
    cursor = await checkpointer.conn.execute(
        "SELECT thread_id, checkpoint_id FROM checkpoints ORDER BY thread_id, checkpoint_id"
    )
    try:
        assert await cursor.fetchall() == [
            ("agent-root", "root-002"),
            ("agent-root", "root-003"),
            (child.child_thread_id, "child-002"),
            (child.child_thread_id, "child-003"),
        ]
    finally:
        await cursor.close()
    await reset_checkpointer()


async def test_cleanup_unreachable_checkpoints_removes_inactive_child_thread(
    client,
    session,
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()
    task = Task(
        id="task-root",
        project_id="project-root",
        title="Root session",
        mode="agent",
        agent_session_id="agent-root",
    )
    session.add(task)
    await session.commit()
    active_child = await create_child_run(
        session,
        parent_session_id="agent-root",
        parent_task_id=task.id,
        parent_thread_id="agent-root",
        child_thread_id="agent-root:child:active",
        agent_key="writer",
        dispatch_id="active",
        tool_call_id="tool-active",
        request={"task": "write", "input": {}, "metadata": {}},
    )
    inactive_child = await create_child_run(
        session,
        parent_session_id="agent-root",
        parent_task_id=task.id,
        parent_thread_id="agent-root",
        child_thread_id="agent-root:child:inactive",
        agent_key="writer",
        dispatch_id="inactive",
        tool_call_id="tool-inactive",
        request={"task": "write", "input": {}, "metadata": {}},
    )
    inactive_child.is_active = False
    await session.commit()

    checkpointer = await get_checkpointer()
    for thread_id in (
        "agent-root",
        active_child.child_thread_id,
        inactive_child.child_thread_id,
    ):
        await checkpointer.conn.execute(
            "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id) VALUES (?, ?, ?)",
            (thread_id, "", f"checkpoint-{thread_id}"),
        )
        await checkpointer.conn.execute(
            "INSERT INTO writes(thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (thread_id, "", f"checkpoint-{thread_id}", "task", 0, "messages"),
        )
    await checkpointer.conn.commit()

    deleted_rows = await cleanup_unreachable_checkpoints(session, checkpointer)

    assert deleted_rows == 2
    cursor = await checkpointer.conn.execute(
        "SELECT thread_id FROM checkpoints ORDER BY thread_id"
    )
    try:
        assert await cursor.fetchall() == [
            ("agent-root",),
            (active_child.child_thread_id,),
        ]
    finally:
        await cursor.close()
    cursor = await checkpointer.conn.execute(
        "SELECT thread_id FROM writes ORDER BY thread_id"
    )
    try:
        assert await cursor.fetchall() == [
            ("agent-root",),
            (active_child.child_thread_id,),
        ]
    finally:
        await cursor.close()
    await reset_checkpointer()


async def test_vacuum_checkpoint_database_only_runs_above_free_space_threshold(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()
    checkpointer = await get_checkpointer()
    await checkpointer.conn.execute("PRAGMA page_size = 4096")
    await checkpointer.conn.execute("PRAGMA journal_mode = DELETE")
    await checkpointer.conn.execute("CREATE TABLE test_data (value BLOB)")
    await checkpointer.conn.execute(
        "INSERT INTO test_data(value) VALUES (zeroblob(32768))"
    )
    await checkpointer.conn.execute("DELETE FROM test_data")
    await checkpointer.conn.commit()
    await reset_checkpointer()

    assert await vacuum_checkpoint_database(min_free_bytes=1) is True


async def test_vacuum_checkpoint_database_skips_small_free_space(
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "test_checkpoints.db"
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(db_path))
    await reset_checkpointer()
    checkpointer = await get_checkpointer()
    await checkpointer.conn.execute("CREATE TABLE test_data (value BLOB)")
    await checkpointer.conn.execute(
        "INSERT INTO test_data(value) VALUES (zeroblob(4096))"
    )
    await checkpointer.conn.execute("DELETE FROM test_data")
    await checkpointer.conn.commit()
    await reset_checkpointer()

    assert await vacuum_checkpoint_database() is False


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
