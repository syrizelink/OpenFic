import os
import shutil
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

import app.settings as app_settings

_checkpointer: AsyncSqliteSaver | None = None


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
        _checkpointer = AsyncSqliteSaver(conn)
        await _checkpointer.setup()
    return _checkpointer


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
