import os
import shutil
from pathlib import Path

import aiosqlite
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint, copy_checkpoint
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

import app.settings as app_settings
from app.agent_runtime.model_config import without_api_key
from app.agent_runtime.persistence.model import AgentChildRun
from app.storage.models.task import Task

_checkpointer: AsyncSqliteSaver | None = None

_ALLOWED_MSGPACK_MODULES = (
    ("app.agent_runtime.tools.impls.interaction.ask_user", "Question"),
    ("app.agent_runtime.tools.impls.interaction.ask_user", "QuestionOption"),
)
_LEGACY_API_KEY_MARKER = b"api_key"
_LEGACY_API_KEY_MIGRATION = "remove_plaintext_api_keys_v1"
_CHECKPOINT_CLEANUP_BATCH_SIZE = 500


def _default_db_path() -> Path:
    return app_settings.settings.checkpoint_db_path


def _legacy_runtime_db_path() -> Path:
    return app_settings.BACKEND_DIR.parent / "data" / "agent" / "langgraph_checkpoints.db"


def _legacy_backend_db_path() -> Path:
    return app_settings.BACKEND_DATA_DIR / "agent_checkpoints.db"


def _migrate_default_checkpoint_db(target_path: Path) -> None:
    legacy_runtime_path = _legacy_runtime_db_path()
    legacy_backend_path = _legacy_backend_db_path()

    target_path.parent.mkdir(parents=True, exist_ok=True)

    if not target_path.exists() and legacy_runtime_path.exists():
        shutil.move(str(legacy_runtime_path), str(target_path))

    if target_path.exists() and legacy_backend_path.exists():
        legacy_backend_path.unlink()


def _get_db_path() -> str:
    db_path = os.environ.get("AGENT_CHECKPOINT_DB")
    if db_path:
        return db_path

    target_path = _default_db_path()
    _migrate_default_checkpoint_db(target_path)
    return str(target_path)


async def get_checkpointer() -> AsyncSqliteSaver:
    global _checkpointer
    if _checkpointer is None:
        db_path = _get_db_path()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(db_path)
        _checkpointer = AsyncSqliteSaver(
            conn,
            serde=JsonPlusSerializer(
                allowed_msgpack_modules=_ALLOWED_MSGPACK_MODULES,
            ),
        )
        await _checkpointer.setup()
        await _remove_api_keys_from_existing_checkpoints(_checkpointer)
    return _checkpointer


async def _remove_api_keys_from_existing_checkpoints(
    checkpointer: AsyncSqliteSaver,
) -> None:
    """Rewrite legacy Agent checkpoints that persisted plaintext API keys."""
    if await _has_completed_legacy_api_key_migration(checkpointer):
        return

    checkpoints: list[tuple[RunnableConfig, Checkpoint]] = []
    for config in await _list_legacy_api_key_checkpoint_configs(checkpointer):
        item = await checkpointer.aget_tuple(config)
        if item is None:
            continue
        channel_values = item.checkpoint.get("channel_values")
        if not isinstance(channel_values, dict):
            continue
        model_config = channel_values.get("model_config")
        if not isinstance(model_config, dict) or "api_key" not in model_config:
            continue
        sanitized_checkpoint = copy_checkpoint(item.checkpoint)
        sanitized_channel_values = sanitized_checkpoint["channel_values"]
        sanitized_channel_values["model_config"] = without_api_key(model_config)
        sanitized_checkpoint["channel_values"] = sanitized_channel_values
        checkpoints.append((item.config, sanitized_checkpoint))

    for config, checkpoint in checkpoints:
        await checkpointer.aput(
            config,
            checkpoint,
            {},
            checkpoint.get("channel_versions", {}),
        )

    await _mark_legacy_api_key_migration_completed(checkpointer)


async def _has_completed_legacy_api_key_migration(
    checkpointer: AsyncSqliteSaver,
) -> bool:
    cursor = await checkpointer.conn.execute(
        """
        CREATE TABLE IF NOT EXISTS openfic_checkpoint_migrations (
            name TEXT PRIMARY KEY
        )
        """
    )
    await cursor.close()
    cursor = await checkpointer.conn.execute(
        "SELECT 1 FROM openfic_checkpoint_migrations WHERE name = ?",
        (_LEGACY_API_KEY_MIGRATION,),
    )
    try:
        return await cursor.fetchone() is not None
    finally:
        await cursor.close()


async def _list_legacy_api_key_checkpoint_configs(
    checkpointer: AsyncSqliteSaver,
) -> list[RunnableConfig]:
    cursor = await checkpointer.conn.execute(
        """
        SELECT thread_id, checkpoint_ns, checkpoint_id
        FROM checkpoints
        WHERE instr(checkpoint, ?) > 0
        """,
        (_LEGACY_API_KEY_MARKER,),
    )
    try:
        rows = await cursor.fetchall()
    finally:
        await cursor.close()

    return [
        {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }
        for thread_id, checkpoint_ns, checkpoint_id in rows
    ]


async def _mark_legacy_api_key_migration_completed(
    checkpointer: AsyncSqliteSaver,
) -> None:
    cursor = await checkpointer.conn.execute(
        "INSERT INTO openfic_checkpoint_migrations (name) VALUES (?)",
        (_LEGACY_API_KEY_MIGRATION,),
    )
    try:
        await checkpointer.conn.commit()
    finally:
        await cursor.close()


async def delete_checkpoints_for_thread(thread_id: str) -> int:
    if not thread_id:
        return 0

    db_path = _get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(db_path)
    try:
        before = conn.total_changes
        await conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
        await conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        await conn.commit()
        return conn.total_changes - before
    finally:
        await conn.close()


async def delete_checkpoints_after_for_thread(
    thread_id: str, after_checkpoint_id: str
) -> int:
    # LangGraph checkpoint_id is UUID v6 (time-ordered), so lexicographic
    # comparison is equivalent to chronological order across all namespaces
    # (root + subgraphs).
    if not thread_id or not after_checkpoint_id:
        return 0

    db_path = _get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(db_path)
    try:
        before = conn.total_changes
        await conn.execute(
            "DELETE FROM writes WHERE thread_id = ? AND checkpoint_id > ?",
            (thread_id, after_checkpoint_id),
        )
        await conn.execute(
            "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_id > ?",
            (thread_id, after_checkpoint_id),
        )
        await conn.commit()
        return conn.total_changes - before
    finally:
        await conn.close()


async def cleanup_unreachable_checkpoints(
    session: AsyncSession,
    checkpointer: AsyncSqliteSaver,
) -> int:
    reachable_thread_ids = await _list_reachable_checkpoint_thread_ids(session)
    checkpoint_thread_ids = await _list_checkpoint_thread_ids(checkpointer)
    unreachable_thread_ids = checkpoint_thread_ids - reachable_thread_ids
    if not unreachable_thread_ids:
        return 0

    deleted_rows = 0
    thread_ids = list(unreachable_thread_ids)
    for index in range(0, len(thread_ids), _CHECKPOINT_CLEANUP_BATCH_SIZE):
        batch = thread_ids[index : index + _CHECKPOINT_CLEANUP_BATCH_SIZE]
        placeholders = ", ".join("?" for _ in batch)
        before = checkpointer.conn.total_changes
        await checkpointer.conn.execute(
            f"DELETE FROM writes WHERE thread_id IN ({placeholders})",
            tuple(batch),
        )
        await checkpointer.conn.execute(
            f"DELETE FROM checkpoints WHERE thread_id IN ({placeholders})",
            tuple(batch),
        )
        deleted_rows += checkpointer.conn.total_changes - before
    await checkpointer.conn.commit()
    return deleted_rows


async def _list_reachable_checkpoint_thread_ids(session: AsyncSession) -> set[str]:
    task_result = await session.execute(
        select(col(Task.agent_session_id)).where(
            col(Task.agent_session_id).is_not(None),
            col(Task.agent_session_id) != "",
        )
    )
    reachable_thread_ids = {
        session_id
        for session_id in task_result.scalars().all()
        if isinstance(session_id, str) and session_id
    }
    if not reachable_thread_ids:
        return reachable_thread_ids

    child_run_result = await session.execute(
        select(
            col(AgentChildRun.parent_session_id),
            col(AgentChildRun.child_thread_id),
        )
    )
    children_by_parent: dict[str, set[str]] = {}
    for parent_session_id, child_thread_id in child_run_result.all():
        if not parent_session_id or not child_thread_id:
            continue
        children_by_parent.setdefault(parent_session_id, set()).add(child_thread_id)

    pending_thread_ids = list(reachable_thread_ids)
    while pending_thread_ids:
        parent_session_id = pending_thread_ids.pop()
        for child_thread_id in children_by_parent.get(parent_session_id, set()):
            if child_thread_id in reachable_thread_ids:
                continue
            reachable_thread_ids.add(child_thread_id)
            pending_thread_ids.append(child_thread_id)

    return reachable_thread_ids


async def _list_checkpoint_thread_ids(checkpointer: AsyncSqliteSaver) -> set[str]:
    cursor = await checkpointer.conn.execute(
        "SELECT thread_id FROM checkpoints UNION SELECT thread_id FROM writes"
    )
    try:
        return {row[0] for row in await cursor.fetchall() if row[0]}
    finally:
        await cursor.close()


async def latest_checkpoint_id_for_thread(thread_id: str) -> str | None:
    if not thread_id:
        return None

    db_path = _get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(db_path)
    try:
        cursor = await conn.execute(
            "SELECT checkpoint_id FROM checkpoints WHERE thread_id = ? "
            "ORDER BY checkpoint_id DESC LIMIT 1",
            (thread_id,),
        )
        row = await cursor.fetchone()
        return str(row[0]) if row and row[0] else None
    finally:
        await conn.close()


async def init_checkpointer() -> AsyncSqliteSaver:
    return await get_checkpointer()


async def close_checkpointer() -> None:
    await reset_checkpointer()


async def reset_checkpointer() -> None:
    global _checkpointer
    checkpointer = _checkpointer
    _checkpointer = None
    if checkpointer is not None:
        await checkpointer.conn.close()
