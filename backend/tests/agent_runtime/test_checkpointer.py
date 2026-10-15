from contextlib import AsyncExitStack, closing
from dataclasses import dataclass
import os
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock, call
from uuid import uuid4

import app.agent_runtime.runner.checkpointer as checkpointer_mod
import aiosqlite
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import pytest
from sqlalchemy import select
from app.agent_runtime.runner.checkpointer import (
    checkpoint_free_page_bytes,
    cleanup_unreachable_checkpoints,
    close_checkpointer,
    delete_checkpoints_after_for_thread,
    delete_checkpoints_for_thread,
    get_checkpointer,
    init_checkpointer,
    latest_checkpoint_id_for_thread,
    prune_checkpoints_for_thread,
    prune_reachable_checkpoints,
    prune_thread_checkpoints,
    reset_checkpointer,
    vacuum_checkpoint_database,
)
from app.agent_runtime.tools.impls.interaction.ask_user import Question, QuestionOption
from app.agent_runtime.persistence.child_runs import create_child_run
from app.agent_runtime.persistence.model import AgentChildRunRequest
from app.storage.models.revision import Revision
from app.storage.models.project import Project
from app.storage.models.task import Task

pytestmark = pytest.mark.usefixtures("fast_checkpoint_sqlite")


@pytest.fixture(autouse=True)
def use_sqlite_checkpointer_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep SQLite-specific checkpoint tests independent from the host backend."""
    monkeypatch.setattr(checkpointer_mod.app_settings.settings, "database_backend", "sqlite")
    monkeypatch.setattr(checkpointer_mod.app_settings.settings, "checkpoint_database_url", None)


@dataclass(frozen=True)
class _CheckpointTaskState:
    message: AIMessage


def test_checkpoint_serializer_sanitizes_cyclic_ai_message() -> None:
    serializer = checkpointer_mod._CheckpointSerializer(
        allowed_msgpack_modules=checkpointer_mod._ALLOWED_MSGPACK_MODULES,
    )
    message = AIMessage(content="complete output")
    message.response_metadata["self"] = message

    message_type, payload = serializer.dumps_typed([message])

    assert message_type == "msgpack"
    assert payload


def test_checkpoint_serializer_sanitizes_message_inside_dataclass() -> None:
    serializer = checkpointer_mod._CheckpointSerializer(
        allowed_msgpack_modules=checkpointer_mod._ALLOWED_MSGPACK_MODULES,
    )
    message = AIMessage(content="complete output")
    message.response_metadata["self"] = message

    message_type, payload = serializer.dumps_typed([_CheckpointTaskState(message)])

    assert message_type == "msgpack"
    assert payload


def test_checkpoint_serializer_falls_back_for_unknown_message_wrapper() -> None:
    class MessageWrapper:
        def __init__(self, message: AIMessage) -> None:
            self.message = message

    serializer = checkpointer_mod._CheckpointSerializer(
        allowed_msgpack_modules=checkpointer_mod._ALLOWED_MSGPACK_MODULES,
    )
    message = AIMessage(content="complete output")
    message.response_metadata["self"] = message

    message_type, payload = serializer.dumps_typed([MessageWrapper(message)])

    assert message_type == "msgpack"
    assert payload


def test_checkpoint_serializer_stringifies_out_of_range_integer_metadata() -> None:
    serializer = checkpointer_mod._CheckpointSerializer(
        allowed_msgpack_modules=checkpointer_mod._ALLOWED_MSGPACK_MODULES,
    )
    oversized_integer = 1 << 100
    message = AIMessage(
        content="complete output",
        response_metadata={"provider_counter": oversized_integer},
    )

    message_type, payload = serializer.dumps_typed([message])
    restored = serializer.loads_typed((message_type, payload))

    assert restored[0].response_metadata["provider_counter"] == str(oversized_integer)


def test_checkpoint_serializer_skips_sanitization_for_serializable_values(monkeypatch) -> None:
    serializer = checkpointer_mod._CheckpointSerializer(
        allowed_msgpack_modules=checkpointer_mod._ALLOWED_MSGPACK_MODULES,
    )
    sanitize_calls = 0
    original_sanitize = checkpointer_mod._sanitize_checkpoint_value

    def track_sanitize(value, active_ids=None):
        nonlocal sanitize_calls
        sanitize_calls += 1
        return original_sanitize(value, active_ids)

    monkeypatch.setattr(checkpointer_mod, "_sanitize_checkpoint_value", track_sanitize)

    message_type, payload = serializer.dumps_typed({"message": "complete"})

    assert message_type == "msgpack"
    assert payload
    assert sanitize_calls == 0


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


@pytest.mark.asyncio
async def test_get_checkpointer_dispatches_to_postgresql_without_sqlite_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("langgraph.checkpoint.postgres.aio")
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    database_url = "postgresql://user:password@localhost/checkpoints"
    postgres_saver = SimpleNamespace(setup=AsyncMock())
    postgres_context = AsyncMock()
    postgres_context.__aenter__.return_value = postgres_saver
    postgres_context.__aexit__.return_value = False
    from_conn_string = Mock(return_value=postgres_context)
    monkeypatch.setattr(AsyncPostgresSaver, "from_conn_string", from_conn_string)
    monkeypatch.setattr(
        checkpointer_mod.app_settings,
        "settings",
        SimpleNamespace(
            database_backend="postgresql",
            checkpoint_database_url=database_url,
        ),
    )
    sqlite_connect = AsyncMock(side_effect=AssertionError("SQLite must not be opened"))
    monkeypatch.setattr(checkpointer_mod.aiosqlite, "connect", sqlite_connect)
    monkeypatch.setattr(
        checkpointer_mod,
        "_get_db_path",
        Mock(side_effect=AssertionError("SQLite path must not be read")),
    )

    await reset_checkpointer()
    try:
        assert await get_checkpointer() is postgres_saver
        from_conn_string.assert_called_once()
        assert from_conn_string.call_args.args == (database_url,)
        postgres_saver.setup.assert_awaited_once()
        sqlite_connect.assert_not_awaited()
    finally:
        await reset_checkpointer()


async def test_postgresql_without_checkpoint_url_uses_sqlite_for_checkpoint_lifecycle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(checkpointer_mod.app_settings.settings, "database_backend", "postgresql")
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(tmp_path / "fallback.db"))
    await reset_checkpointer()
    try:
        saver = await get_checkpointer()
        assert isinstance(saver, AsyncSqliteSaver)
        for checkpoint_id in ("cp-001", "cp-002"):
            await saver.conn.execute(
                "INSERT INTO checkpoints(thread_id, checkpoint_ns, checkpoint_id) VALUES (?, ?, ?)",
                ("fallback-thread", "", checkpoint_id),
            )
        await saver.conn.commit()
        assert await latest_checkpoint_id_for_thread("fallback-thread") == "cp-002"
        assert await delete_checkpoints_after_for_thread("fallback-thread", "cp-001") == 1
        assert await delete_checkpoints_for_thread("fallback-thread") == 1
        assert await checkpoint_free_page_bytes() != (0, 0)
    finally:
        await reset_checkpointer()


async def test_failed_sqlite_checkpoint_setup_closes_connection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(checkpointer_mod.app_settings.settings, "database_backend", "postgresql")
    monkeypatch.setenv("AGENT_CHECKPOINT_DB", str(tmp_path / "failed.db"))
    await reset_checkpointer()
    original_connect = aiosqlite.connect
    connections = []

    async def connect(*args, **kwargs):
        conn = await original_connect(*args, **kwargs)
        connections.append(conn)
        return conn

    monkeypatch.setattr(aiosqlite, "connect", connect)
    monkeypatch.setattr(AsyncSqliteSaver, "setup", AsyncMock(side_effect=RuntimeError("setup failed")))
    try:
        with pytest.raises(RuntimeError, match="setup failed"):
            await get_checkpointer()
        assert checkpointer_mod._checkpointer is None
        assert len(connections) == 1
        with pytest.raises(ValueError, match="no active connection"):
            await connections[0].execute("SELECT 1")
    finally:
        for conn in connections:
            await conn.close()
        await reset_checkpointer()


async def test_explicit_postgresql_checkpoint_failure_does_not_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkpointer_mod.app_settings.settings, "database_backend", "postgresql")
    monkeypatch.setattr(checkpointer_mod.app_settings.settings, "checkpoint_database_url", "postgresql://localhost/unavailable")
    monkeypatch.setattr(checkpointer_mod, "_create_postgresql_checkpointer", AsyncMock(side_effect=RuntimeError("PostgreSQL unavailable")))
    connect = Mock(side_effect=AssertionError("must not silently switch checkpoint storage"))
    monkeypatch.setattr(aiosqlite, "connect", connect)
    await reset_checkpointer()
    with pytest.raises(RuntimeError, match="PostgreSQL unavailable"):
        await get_checkpointer()
    assert checkpointer_mod._checkpointer is None
    connect.assert_not_called()


@pytest.mark.asyncio
async def test_reset_checkpointer_closes_postgresql_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    postgres_context = AsyncMock()
    postgres_context.__aexit__.return_value = False
    context_stack = AsyncExitStack()
    await context_stack.enter_async_context(postgres_context)
    checkpointer_mod._checkpointer = SimpleNamespace()
    checkpointer_mod._checkpointer_context = context_stack

    await reset_checkpointer()

    postgres_context.__aexit__.assert_awaited_once()
    assert postgres_context.__aexit__.await_args.args[-3:] == (None, None, None)
    assert checkpointer_mod._checkpointer is None


@pytest.mark.asyncio
async def test_latest_checkpoint_id_for_postgresql_uses_saver_public_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint = SimpleNamespace(
        config={
            "configurable": {
                "thread_id": "session-a",
                "checkpoint_id": "pg-latest",
            }
        }
    )

    async def list_checkpoints(*args, **kwargs):
        yield checkpoint

    alist = Mock(side_effect=list_checkpoints)
    monkeypatch.setattr(
        checkpointer_mod,
        "get_checkpointer",
        AsyncMock(return_value=SimpleNamespace(alist=alist)),
    )
    monkeypatch.setattr(
        checkpointer_mod.app_settings,
        "settings",
        SimpleNamespace(database_backend="postgresql", checkpoint_database_url="postgresql://localhost/checkpoints"),
    )

    assert await latest_checkpoint_id_for_thread("session-a") == "pg-latest"
    alist.assert_called_once_with(
        {"configurable": {"thread_id": "session-a"}},
        limit=1,
    )


@pytest.mark.asyncio
async def test_delete_checkpoints_for_postgresql_is_transactional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transaction = AsyncMock()
    cursor = SimpleNamespace(
        execute=AsyncMock(), rowcount=2,
        connection=SimpleNamespace(transaction=Mock(return_value=transaction)),
    )
    cursor_context = AsyncMock()
    cursor_context.__aenter__.return_value = cursor
    saver = SimpleNamespace(_cursor=Mock(return_value=cursor_context))
    monkeypatch.setattr(
        checkpointer_mod,
        "get_checkpointer",
        AsyncMock(return_value=saver),
    )
    monkeypatch.setattr(
        checkpointer_mod.app_settings,
        "settings",
        SimpleNamespace(database_backend="postgresql", checkpoint_database_url="postgresql://localhost/checkpoints"),
    )

    assert await delete_checkpoints_for_thread("session-a") == 6
    transaction.__aenter__.assert_awaited_once()
    transaction.__aexit__.assert_awaited_once_with(None, None, None)
    assert cursor.execute.await_args_list[:2] == [
        call("DELETE FROM checkpoint_writes WHERE thread_id = %s", ("session-a",)),
        call("DELETE FROM checkpoints WHERE thread_id = %s", ("session-a",)),
    ]


@pytest.mark.asyncio
async def test_delete_checkpoints_after_for_postgresql_deletes_rows_after_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transaction = AsyncMock()
    cursor = SimpleNamespace(rowcount=2, connection=SimpleNamespace(transaction=Mock(return_value=transaction)))
    cursor_context = AsyncMock()
    cursor_context.__aenter__.return_value = cursor
    postgres_saver = SimpleNamespace(
        _cursor=Mock(return_value=cursor_context),
    )
    execute = AsyncMock(side_effect=[None, None, None])
    cursor.execute = execute
    monkeypatch.setattr(
        checkpointer_mod,
        "get_checkpointer",
        AsyncMock(return_value=postgres_saver),
    )
    monkeypatch.setattr(
        checkpointer_mod.app_settings,
        "settings",
        SimpleNamespace(database_backend="postgresql", checkpoint_database_url="postgresql://localhost/checkpoints"),
    )

    assert await delete_checkpoints_after_for_thread("session-a", "cp-001") == 6
    transaction.__aenter__.assert_awaited_once()
    transaction.__aexit__.assert_awaited_once_with(None, None, None)

    postgres_saver._cursor.assert_called_once_with()
    assert execute.await_args_list == [
        call(
            "DELETE FROM checkpoint_writes "
            "WHERE thread_id = %s AND checkpoint_id > %s",
            ("session-a", "cp-001"),
        ),
        call(
            "DELETE FROM checkpoints "
            "WHERE thread_id = %s AND checkpoint_id > %s",
            ("session-a", "cp-001"),
        ),
        call(
            "DELETE FROM checkpoint_blobs AS blobs "
            "WHERE blobs.thread_id = %s "
            "AND NOT EXISTS ("
            "SELECT 1 FROM checkpoints AS checkpoints "
            "CROSS JOIN LATERAL jsonb_each_text(checkpoints.checkpoint->'channel_versions') "
            "AS versions(channel, version) "
            "WHERE checkpoints.thread_id = blobs.thread_id "
            "AND checkpoints.checkpoint_ns = blobs.checkpoint_ns "
            "AND versions.channel = blobs.channel "
            "AND versions.version = blobs.version"
            ")",
            ("session-a",),
        ),
    ]


async def test_prune_thread_checkpoints_for_postgresql_uses_rollback_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkpointer_mod.app_settings.settings, "database_backend", "postgresql")
    retained = AsyncMock(return_value={"session-a": {"root-boundary", "child-boundary"}})
    prune = AsyncMock(return_value=7)
    monkeypatch.setattr(checkpointer_mod, "_list_retained_checkpoint_ids", retained)
    monkeypatch.setattr(checkpointer_mod, "prune_checkpoints_for_thread", prune)
    session = Mock()
    saver = Mock()

    assert await prune_thread_checkpoints(session, saver, "session-a") == 7
    retained.assert_awaited_once_with(session, {"session-a"})
    prune.assert_awaited_once_with(saver, "session-a", {"root-boundary", "child-boundary"})


@pytest.fixture
async def postgresql_pruning_saver(monkeypatch: pytest.MonkeyPatch):
    database_url = os.getenv("OPENFIC_TEST_CHECKPOINT_DATABASE_URL")
    if not database_url:
        pytest.skip("Set OPENFIC_TEST_CHECKPOINT_DATABASE_URL to test PostgreSQL pruning")
    psycopg = pytest.importorskip("psycopg")
    postgres = pytest.importorskip("langgraph.checkpoint.postgres.aio")
    monkeypatch.setattr(checkpointer_mod.app_settings.settings, "database_backend", "postgresql")
    monkeypatch.setattr(checkpointer_mod.app_settings.settings, "checkpoint_database_url", database_url)
    schema = f"checkpoint_pruning_{uuid4().hex}"
    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as conn:
        await conn.execute(f'CREATE SCHEMA "{schema}"')
        try:
            await conn.execute(f'SET search_path TO "{schema}"')
            saver = postgres.AsyncPostgresSaver(conn)
            await saver.setup()
            for thread_id, namespace, checkpoint_id, version in [
                ("session-a", "", "cp-001", "1"),
                ("session-a", "", "cp-002", "2"),
                ("session-a", "", "cp-003", "2"),
                ("session-a", "child", "cp-004", "1"),
                ("session-a", "child", "cp-005", "2"),
                ("session-b", "", "cp-001", "1"),
            ]:
                config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": namespace}}
                checkpoint = {
                    "v": 4,
                    "id": checkpoint_id,
                    "ts": "2026-10-14T00:00:00+00:00",
                    "channel_values": {"messages": [AIMessage(content=f"{namespace}:{version}")]},
                    "channel_versions": {"messages": version},
                    "versions_seen": {},
                    "pending_sends": [],
                }
                saved = await saver.aput(config, checkpoint, {}, {"messages": version})
                await saver.aput_writes(saved, [("messages", "pending")], "task")
            yield saver
        finally:
            await conn.execute(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.mark.parametrize("retained_ids", [set(), {"cp-002", "cp-004"}])
async def test_postgresql_pruning_preserves_latest_rollback_and_shared_blobs(
    postgresql_pruning_saver,
    retained_ids: set[str],
) -> None:
    saver = postgresql_pruning_saver
    deleted = await prune_checkpoints_for_thread(saver, "session-a", retained_ids)

    expected = {"cp-003", "cp-005"} | retained_ids
    assert deleted == (5 - len(expected)) * 2 + (2 if not retained_ids else 1)
    async with saver._cursor() as cursor:
        for table in ("checkpoints", "checkpoint_writes"):
            await cursor.execute(f"SELECT checkpoint_id FROM {table} WHERE thread_id = %s", ("session-a",))
            assert {row["checkpoint_id"] for row in await cursor.fetchall()} == expected
            await cursor.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE thread_id = %s", ("session-b",))
            assert (await cursor.fetchone())["count"] == 1
        await cursor.execute("SELECT checkpoint_ns, version FROM checkpoint_blobs WHERE thread_id = %s", ("session-a",))
        blobs = {(row["checkpoint_ns"], row["version"]) for row in await cursor.fetchall()}
        assert blobs == ({("", "2"), ("child", "2")} | ({("child", "1")} if retained_ids else set()))
        await cursor.execute("SELECT COUNT(*) AS count FROM checkpoint_blobs WHERE thread_id = %s", ("session-b",))
        assert (await cursor.fetchone())["count"] == 1
    for namespace, checkpoint_id, version in [
        ("", "cp-003", "2"), ("child", "cp-005", "2"),
        *([("", "cp-002", "2"), ("child", "cp-004", "1")] if retained_ids else []),
    ]:
        restored = await saver.aget_tuple({"configurable": {
            "thread_id": "session-a", "checkpoint_ns": namespace, "checkpoint_id": checkpoint_id,
        }})
        assert restored.checkpoint["channel_values"]["messages"][0].content == f"{namespace}:{version}"
        assert restored.pending_writes
    assert await prune_checkpoints_for_thread(saver, "session-a", retained_ids) == 0
    assert await prune_checkpoints_for_thread(saver, "missing", set()) == 0
    assert await prune_checkpoints_for_thread(saver, "", set()) == 0


async def test_postgresql_pruning_rolls_back_all_deletes_on_failure(postgresql_pruning_saver) -> None:
    errors = pytest.importorskip("psycopg.errors")
    saver = postgresql_pruning_saver
    async with saver._cursor() as cursor:
        await cursor.execute("""
            CREATE FUNCTION reject_blob_delete() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'pruning failure'; END $$
        """)
        await cursor.execute("""
            CREATE TRIGGER reject_blob_delete BEFORE DELETE ON checkpoint_blobs
            FOR EACH ROW EXECUTE FUNCTION reject_blob_delete()
        """)
    with pytest.raises(errors.RaiseException, match="pruning failure"):
        await prune_checkpoints_for_thread(saver, "session-a", set())
    async with saver._cursor() as cursor:
        for table, expected_count in [("checkpoints", 5), ("checkpoint_writes", 5), ("checkpoint_blobs", 4)]:
            await cursor.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE thread_id = %s", ("session-a",))
            assert (await cursor.fetchone())["count"] == expected_count


@pytest.mark.parametrize("delete_all", [False, True])
async def test_postgresql_checkpoint_deletion_rolls_back_on_failure(
    postgresql_pruning_saver, monkeypatch: pytest.MonkeyPatch, delete_all: bool,
) -> None:
    saver = postgresql_pruning_saver
    monkeypatch.setattr(checkpointer_mod, "get_checkpointer", AsyncMock(return_value=saver))
    errors = pytest.importorskip("psycopg.errors")
    async with saver._cursor() as cursor:
        await cursor.execute("""
            CREATE FUNCTION reject_blob_delete() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'rollback failure'; END $$
        """)
        await cursor.execute("""
            CREATE TRIGGER reject_blob_delete BEFORE DELETE ON checkpoint_blobs
            FOR EACH ROW EXECUTE FUNCTION reject_blob_delete()
        """)
    with pytest.raises(errors.RaiseException, match="rollback failure"):
        if delete_all:
            await delete_checkpoints_for_thread("session-a")
        else:
            await delete_checkpoints_after_for_thread("session-a", "cp-001")
    async with saver._cursor() as cursor:
        for table, expected_count in [("checkpoints", 5), ("checkpoint_writes", 5), ("checkpoint_blobs", 4)]:
            await cursor.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE thread_id = %s", ("session-a",))
            assert (await cursor.fetchone())["count"] == expected_count


async def test_postgresql_startup_cleanup_removes_orphans_and_prunes_reachable_history(
    postgresql_pruning_saver, monkeypatch: pytest.MonkeyPatch,
) -> None:
    saver = postgresql_pruning_saver
    monkeypatch.setattr(checkpointer_mod, "_list_reachable_checkpoint_thread_ids", AsyncMock(return_value={"session-a"}))
    monkeypatch.setattr(checkpointer_mod, "_list_retained_checkpoint_ids", AsyncMock(return_value={"session-a": {"cp-002", "cp-004"}}))
    session = Mock()
    assert await cleanup_unreachable_checkpoints(session, saver) == 3
    assert await prune_reachable_checkpoints(session, saver) == 3
    async with saver._cursor() as cursor:
        for table in ("checkpoints", "checkpoint_writes", "checkpoint_blobs"):
            await cursor.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE thread_id = %s", ("session-b",))
            assert (await cursor.fetchone())["count"] == 0
        await cursor.execute("SELECT checkpoint_id FROM checkpoints WHERE thread_id = %s", ("session-a",))
        assert {row["checkpoint_id"] for row in await cursor.fetchall()} == {"cp-002", "cp-003", "cp-004", "cp-005"}
    for namespace, checkpoint_id in [("", "cp-002"), ("", "cp-003"), ("child", "cp-004"), ("child", "cp-005")]:
        assert await saver.aget_tuple({"configurable": {"thread_id": "session-a", "checkpoint_ns": namespace, "checkpoint_id": checkpoint_id}}) is not None
    assert await cleanup_unreachable_checkpoints(session, saver) == 0
    assert await prune_reachable_checkpoints(session, saver) == 0


@pytest.mark.parametrize("thread_id", ["session-a", "write-only"])
async def test_postgresql_pruning_cleans_orphan_writes_and_blobs_without_obsolete_checkpoints(
    postgresql_pruning_saver, thread_id: str,
) -> None:
    saver = postgresql_pruning_saver
    await prune_checkpoints_for_thread(saver, "session-a", set())
    await saver.aput_writes(
        {"configurable": {"thread_id": thread_id, "checkpoint_ns": "", "checkpoint_id": "missing"}},
        [("messages", "orphan")], "orphan-task",
    )
    async with saver._cursor() as cursor:
        await cursor.execute(
            "INSERT INTO checkpoint_blobs (thread_id, checkpoint_ns, channel, version, type, blob) "
            "SELECT %s, checkpoint_ns, channel, 'orphan-version', type, blob "
            "FROM checkpoint_blobs WHERE thread_id = %s LIMIT 1",
            (thread_id, "session-a"),
        )
    assert await prune_checkpoints_for_thread(saver, thread_id, set()) == 2
    assert await prune_checkpoints_for_thread(saver, thread_id, set()) == 0


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
    session.add(Project(id="project-root", title="Root project"))
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
        parent_task_id=task.id,
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
    session.add(Project(id="project-root", title="Root project"))
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
    session.add(Project(id="project-root", title="Root project"))
    task = Task(
        id="task-root",
        project_id="project-root",
        title="Root session",
        mode="agent",
        agent_session_id="agent-root",
    )
    session.add(task)
    await session.commit()
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
    session.add(Project(id="project-root", title="Root project"))
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
