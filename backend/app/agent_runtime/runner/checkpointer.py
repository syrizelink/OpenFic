import asyncio
import os
import shutil
import time
from collections.abc import Callable
from contextlib import suppress
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
from app.agent_runtime.persistence.model import AgentChildRun, AgentChildRunRequest
from app.maintenance import maintenance_state
from app.storage.models.revision import Revision
from app.storage.models.task import Task

_checkpointer: AsyncSqliteSaver | None = None

_ALLOWED_MSGPACK_MODULES = (
    ("app.agent_runtime.tools.impls.interaction.ask_user", "Question"),
    ("app.agent_runtime.tools.impls.interaction.ask_user", "QuestionOption"),
)
_LEGACY_API_KEY_MARKER = b"api_key"
_LEGACY_API_KEY_MIGRATION = "remove_plaintext_api_keys_v1"
_INCREMENTAL_AUTO_VACUUM_MIGRATION = "incremental_auto_vacuum_v1"
_CHECKPOINT_CLEANUP_BATCH_SIZE = 500
_VACUUM_MIN_FREE_BYTES = 64 * 1024 * 1024
_INCREMENTAL_VACUUM_BATCH_BYTES = 64 * 1024 * 1024
_VACUUM_PROGRESS_STEP = 10
CheckpointMaintenanceProgress = Callable[[str, float | None, int, int], None]


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


async def _configure_checkpoint_connection(conn: aiosqlite.Connection) -> None:
    for pragma in (
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        "PRAGMA busy_timeout=30000",
    ):
        cursor = await conn.execute(pragma)
        await cursor.close()
    await conn.commit()


async def get_checkpointer() -> AsyncSqliteSaver:
    global _checkpointer
    if _checkpointer is None:
        if maintenance_state.is_checkpoint_locked():
            raise RuntimeError(
                "Checkpoint database maintenance is in progress; agent runs are temporarily unavailable"
            )
        db_path = _get_db_path()
        db_path_exists = Path(db_path).exists()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(db_path)
        if not db_path_exists:
            await conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
            await _mark_incremental_auto_vacuum_migration_completed(conn)
        await _configure_checkpoint_connection(conn)
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


async def _ensure_migrations_table(conn: aiosqlite.Connection) -> None:
    cursor = await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS openfic_checkpoint_migrations (
            name TEXT PRIMARY KEY
        )
        """
    )
    await cursor.close()


async def _has_migration_completed(conn: aiosqlite.Connection, name: str) -> bool:
    cursor = await conn.execute(
        "SELECT 1 FROM openfic_checkpoint_migrations WHERE name = ?",
        (name,),
    )
    try:
        return await cursor.fetchone() is not None
    finally:
        await cursor.close()


async def _mark_incremental_auto_vacuum_migration_completed(
    conn: aiosqlite.Connection,
) -> None:
    await _ensure_migrations_table(conn)
    cursor = await conn.execute(
        "INSERT INTO openfic_checkpoint_migrations (name) VALUES (?)",
        (_INCREMENTAL_AUTO_VACUUM_MIGRATION,),
    )
    try:
        await conn.commit()
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


async def prune_checkpoints_for_thread(
    checkpointer: AsyncSqliteSaver,
    thread_id: str,
    retained_checkpoint_ids: set[str],
) -> int:
    """Retain the latest checkpoint in each namespace and explicit rollback points."""
    if not thread_id:
        return 0

    cursor = await checkpointer.conn.execute(
        "SELECT checkpoint_ns, checkpoint_id FROM checkpoints WHERE thread_id = ?",
        (thread_id,),
    )
    try:
        checkpoint_rows = await cursor.fetchall()
    finally:
        await cursor.close()
    if not checkpoint_rows:
        return 0

    latest_by_namespace: dict[str, str] = {}
    for checkpoint_ns, checkpoint_id in checkpoint_rows:
        if checkpoint_id and checkpoint_id > latest_by_namespace.get(checkpoint_ns, ""):
            latest_by_namespace[checkpoint_ns] = checkpoint_id
    retained_ids = set(latest_by_namespace.values()) | retained_checkpoint_ids
    placeholders = ", ".join("?" for _ in retained_ids)
    before = checkpointer.conn.total_changes
    await checkpointer.conn.execute("BEGIN")
    try:
        await checkpointer.conn.execute(
            f"DELETE FROM writes WHERE thread_id = ? AND checkpoint_id NOT IN ({placeholders})",
            (thread_id, *retained_ids),
        )
        await checkpointer.conn.execute(
            f"DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_id NOT IN ({placeholders})",
            (thread_id, *retained_ids),
        )
        await checkpointer.conn.commit()
    except Exception:
        await checkpointer.conn.rollback()
        raise
    return checkpointer.conn.total_changes - before


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
        ).where(col(AgentChildRun.is_active).is_(True))
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


async def prune_reachable_checkpoints(
    session: AsyncSession,
    checkpointer: AsyncSqliteSaver,
) -> int:
    """Prune internal history while preserving recovery and rollback checkpoints."""
    reachable_thread_ids = await _list_reachable_checkpoint_thread_ids(session)
    return await _prune_checkpoint_threads(session, checkpointer, reachable_thread_ids)


async def prune_thread_checkpoints(
    session: AsyncSession,
    checkpointer: AsyncSqliteSaver,
    thread_id: str,
) -> int:
    """Prune one thread's internal history while preserving recovery and rollback checkpoints.

    Applies the same retention rules as startup pruning: the latest checkpoint in
    each namespace plus explicit rollback points for this thread.
    """
    if not thread_id:
        return 0
    retained_checkpoint_ids = await _list_retained_checkpoint_ids(session, {thread_id})
    return await prune_checkpoints_for_thread(
        checkpointer,
        thread_id,
        retained_checkpoint_ids.get(thread_id, set()),
    )


async def _prune_checkpoint_threads(
    session: AsyncSession,
    checkpointer: AsyncSqliteSaver,
    thread_ids: set[str],
) -> int:
    if not thread_ids:
        return 0

    retained_checkpoint_ids = await _list_retained_checkpoint_ids(session, thread_ids)
    deleted_rows = 0
    for thread_id in thread_ids:
        deleted_rows += await prune_checkpoints_for_thread(
            checkpointer,
            thread_id,
            retained_checkpoint_ids.get(thread_id, set()),
        )
    return deleted_rows


async def _list_retained_checkpoint_ids(
    session: AsyncSession,
    thread_ids: set[str],
) -> dict[str, set[str]]:
    retained_ids: dict[str, set[str]] = {}
    if not thread_ids:
        return retained_ids

    revision_result = await session.execute(
        select(
            col(Revision.graph_thread_id),
            col(Revision.pre_run_checkpoint_id),
        ).where(
            col(Revision.graph_thread_id).in_(thread_ids),
            col(Revision.pre_run_checkpoint_id).is_not(None),
        )
    )
    for thread_id, checkpoint_id in revision_result.all():
        if thread_id and checkpoint_id:
            retained_ids.setdefault(thread_id, set()).add(checkpoint_id)

    child_request_result = await session.execute(
        select(
            col(AgentChildRun.child_thread_id),
            col(AgentChildRunRequest.pre_request_checkpoint_id),
        )
        .join(
            AgentChildRunRequest,
            col(AgentChildRunRequest.child_run_id) == col(AgentChildRun.id),
        )
        .where(
            col(AgentChildRun.is_active).is_(True),
            col(AgentChildRun.child_thread_id).in_(thread_ids),
            col(AgentChildRunRequest.pre_request_checkpoint_id).is_not(None),
        )
    )
    for thread_id, checkpoint_id in child_request_result.all():
        if thread_id and checkpoint_id:
            retained_ids.setdefault(thread_id, set()).add(checkpoint_id)

    return retained_ids


async def _get_pragma_int(conn: aiosqlite.Connection, pragma: str) -> int:
    cursor = await conn.execute(f"PRAGMA {pragma}")
    try:
        row = await cursor.fetchone()
    finally:
        await cursor.close()
    return int(row[0]) if row else 0


async def _truncate_checkpoint_wal(
    conn: aiosqlite.Connection,
    *,
    max_attempts: int = 5,
) -> None:
    """Checkpoint and truncate the WAL before rebuilding the database.

    ``PRAGMA wal_checkpoint(TRUNCATE)`` returns a ``(busy, log, checkpointed)``
    row. A non-zero ``busy`` means a reader still holds the WAL, so the
    checkpoint did not finish and ``VACUUM INTO`` could produce an incomplete
    snapshot. Retry briefly, then fail instead of risking data loss.
    """
    for attempt in range(max_attempts):
        cursor = await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        try:
            row = await cursor.fetchone()
        finally:
            await cursor.close()
        busy = int(row[0]) if row and row[0] is not None else 0
        if not busy:
            return
        if attempt < max_attempts - 1:
            await asyncio.sleep(0.2 * (attempt + 1))
    raise RuntimeError(
        "Checkpoint WAL is busy after retries; another connection still holds "
        "the checkpoint database"
    )


async def _run_full_vacuum(
    conn: aiosqlite.Connection,
    progress_callback: CheckpointMaintenanceProgress | None = None,
    phase: str = "migrating",
    db_path: str | None = None,
) -> None:
    vm_ops = 0
    last_report_at = 0.0

    def on_progress() -> int:
        nonlocal vm_ops, last_report_at
        vm_ops += _VACUUM_PROGRESS_STEP
        now = time.monotonic()
        if progress_callback is not None and now - last_report_at >= 1.0:
            progress_callback(phase, None, vm_ops, 0)
            last_report_at = now
        return 0

    if progress_callback is not None:
        progress_callback(phase, None, 0, 0)
    if db_path:
        folder = Path(db_path).parent
        folder.mkdir(parents=True, exist_ok=True)
        await conn.execute(
            f"PRAGMA temp_store_directory = '{str(folder).replace(chr(39), chr(39)*2)}'"
        )
    # step 必须足够小：SQLite 的 progress handler 按 VM 指令数触发，
    # VACUUM 期间总指令数有限，step 过大（如 10000）会导致完全不回调。
    await conn.set_progress_handler(on_progress, _VACUUM_PROGRESS_STEP)
    try:
        await conn.execute("VACUUM")
    finally:
        await conn.set_progress_handler(lambda: 0, 0)


async def _run_vacuum_into(
    conn: aiosqlite.Connection,
    target: str,
    progress_callback: CheckpointMaintenanceProgress | None = None,
    phase: str = "vacuuming",
    db_path: str | None = None,
) -> None:
    if progress_callback is not None:
        progress_callback(phase, 0.0, 0, 0)
    if db_path:
        folder = Path(db_path).parent
        folder.mkdir(parents=True, exist_ok=True)
        await conn.execute(
            f"PRAGMA temp_store_directory = '{str(folder).replace(chr(39), chr(39)*2)}'"
        )
    await conn.execute(f"VACUUM INTO '{target.replace(chr(39), chr(39)*2)}'")


async def needs_incremental_auto_vacuum_migration() -> bool:
    """Return True if the checkpoint db still needs the INCREMENTAL migration."""
    db_path = _get_db_path()
    if not Path(db_path).exists():
        return False
    conn = await aiosqlite.connect(db_path)
    try:
        await _ensure_migrations_table(conn)
        return not await _has_migration_completed(
            conn, _INCREMENTAL_AUTO_VACUUM_MIGRATION
        )
    finally:
        await conn.close()


async def checkpoint_free_page_bytes() -> tuple[int, int]:
    """Return (free_bytes, live_bytes) for the checkpoint db."""
    db_path = _get_db_path()
    if not Path(db_path).exists():
        return 0, 0
    conn = await aiosqlite.connect(db_path)
    try:
        page_size = await _get_pragma_int(conn, "page_size")
        page_count = await _get_pragma_int(conn, "page_count")
        freelist = await _get_pragma_int(conn, "freelist_count")
    finally:
        await conn.close()
    live_pages = max(0, page_count - freelist)
    return freelist * page_size, live_pages * page_size


async def migrate_checkpoint_database_to_incremental(
    progress_callback: CheckpointMaintenanceProgress | None = None,
) -> bool:
    """Enable incremental auto-vacuum, rebuilding legacy databases once."""
    db_path = _get_db_path()
    if not Path(db_path).exists():
        return False

    conn = await aiosqlite.connect(db_path)
    try:
        await _ensure_migrations_table(conn)
        if await _has_migration_completed(conn, _INCREMENTAL_AUTO_VACUUM_MIGRATION):
            return False

        await conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
        await conn.commit()
        await _run_full_vacuum(conn, progress_callback, db_path=db_path)
        await _mark_incremental_auto_vacuum_migration_completed(conn)
        return True
    finally:
        await conn.close()


async def full_vacuum_checkpoint_database(
    progress_callback: CheckpointMaintenanceProgress | None = None,
) -> bool:
    """Rebuild checkpoint db into a fresh file via VACUUM INTO, then swap it in.

    Unlike a plain VACUUM, this does not need to hold an exclusive lock on the
    source database, so it is significantly faster and leaves the original file
    untouched until the atomic replacement. Progress is reported by polling the
    size of the growing target file, since VACUUM INTO does not invoke the
    progress handler.
    """
    db_path = _get_db_path()
    if not Path(db_path).exists():
        return False

    target = f"{db_path}.vacuuming"
    Path(target).unlink(missing_ok=True)

    conn = await aiosqlite.connect(db_path)
    try:
        await _truncate_checkpoint_wal(conn)
        page_size = await _get_pragma_int(conn, "page_size")
        live_pages = (
            await _get_pragma_int(conn, "page_count")
            - await _get_pragma_int(conn, "freelist_count")
        )
    finally:
        await conn.close()
    estimated_target_bytes = max(1, live_pages * page_size)

    conn = await aiosqlite.connect(db_path)
    try:
        monitor_task = asyncio.create_task(
            _monitor_vacuum_into_target(
                target,
                estimated_target_bytes,
                progress_callback,
            )
        )
        try:
            await _run_vacuum_into(conn, target, None, db_path=db_path)
        except Exception:
            # 写入目标文件失败（如磁盘空间不足），清理残留后向上抛出
            Path(target).unlink(missing_ok=True)
            raise
        finally:
            monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await monitor_task
    finally:
        await conn.close()

    try:
        os.replace(target, db_path)
    except OSError:
        Path(target).unlink(missing_ok=True)
        raise
    # The freshly VACUUMed file contains no WAL frames; drop the previous
    # database's sidecar files so SQLite never replays stale WAL content.
    Path(f"{db_path}-wal").unlink(missing_ok=True)
    Path(f"{db_path}-shm").unlink(missing_ok=True)
    if progress_callback is not None:
        progress_callback("vacuuming", 1.0, estimated_target_bytes, estimated_target_bytes)
    return True


async def _monitor_vacuum_into_target(
    target: str,
    estimated_target_bytes: int,
    progress_callback: CheckpointMaintenanceProgress | None,
) -> None:
    last_report_at = 0.0
    while True:
        current = Path(target).stat().st_size if Path(target).exists() else 0
        now = time.monotonic()
        if progress_callback is not None and now - last_report_at >= 0.5:
            progress = min(1.0, current / estimated_target_bytes)
            progress_callback("vacuuming", progress, current, estimated_target_bytes)
            last_report_at = now
        await asyncio.sleep(0.5)


async def incremental_vacuum_checkpoint_database(
    min_free_bytes: int = _VACUUM_MIN_FREE_BYTES,
    batch_bytes: int = _INCREMENTAL_VACUUM_BATCH_BYTES,
    progress_callback: CheckpointMaintenanceProgress | None = None,
) -> bool:
    """Reclaim free checkpoint pages in bounded incremental batches."""
    db_path = _get_db_path()
    if not Path(db_path).exists():
        return False

    conn = await aiosqlite.connect(db_path)
    try:
        if await _get_pragma_int(conn, "auto_vacuum") != 2:
            return False

        page_size = await _get_pragma_int(conn, "page_size")
        total_free_pages = await _get_pragma_int(conn, "freelist_count")
        if page_size * total_free_pages < min_free_bytes:
            return False

        batch_pages = max(1, batch_bytes // max(page_size, 1))
        remaining_pages = total_free_pages
        while remaining_pages > 0:
            previous_remaining_pages = remaining_pages
            await conn.execute(f"PRAGMA incremental_vacuum({batch_pages})")
            await conn.commit()
            remaining_pages = await _get_pragma_int(conn, "freelist_count")
            reclaimed_pages = total_free_pages - remaining_pages
            progress = reclaimed_pages / total_free_pages
            if progress_callback is not None:
                progress_callback(
                    "vacuuming",
                    progress,
                    reclaimed_pages,
                    total_free_pages,
                )
            if remaining_pages >= previous_remaining_pages:
                break
        return remaining_pages < total_free_pages
    finally:
        await conn.close()


async def vacuum_checkpoint_database(
    min_free_bytes: int = _VACUUM_MIN_FREE_BYTES,
) -> bool:
    """Backward-compatible alias for incremental checkpoint reclamation."""
    return await incremental_vacuum_checkpoint_database(min_free_bytes=min_free_bytes)


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
