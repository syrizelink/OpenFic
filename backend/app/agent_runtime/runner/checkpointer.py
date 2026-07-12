import os
import shutil
from pathlib import Path
import aiosqlite
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint, copy_checkpoint
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

import app.settings as app_settings
from app.agent_runtime.model_config import without_api_key

_checkpointer: AsyncSqliteSaver | None = None

_ALLOWED_MSGPACK_MODULES = (
    ("app.agent_runtime.tools.impls.interaction.ask_user", "Question"),
    ("app.agent_runtime.tools.impls.interaction.ask_user", "QuestionOption"),
)


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
    checkpoints: list[tuple[RunnableConfig, Checkpoint]] = []
    async for item in checkpointer.alist(None):
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
