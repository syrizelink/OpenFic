"""Queued persistence for LLM audit logs."""

from __future__ import annotations

import asyncio
import json

from loguru import logger
from sqlalchemy import func, select
from sqlmodel import col

from app.storage.database import create_session
from app.storage.models.llm_audit_log import LLMAuditLog
from app.storage.repos import setting_repo


AUDIT_DETAILS_PERSISTENCE_SETTING_KEY = "audit_persist_details"


def persist_audit_details(audit_log: LLMAuditLog, should_persist: bool) -> LLMAuditLog:
    """Remove heavy audit payloads while retaining aggregate metrics."""
    if should_persist:
        return audit_log

    audit_log.request_messages = None
    audit_log.tool_references = None
    audit_log.response_content = None
    audit_log.response_tool_calls = None
    audit_log.tool_call_results = None
    audit_log.extra_data = None
    return audit_log


class AuditQueue:
    """Serializes audit writes to reduce backing-store contention."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[LLMAuditLog | None] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._sequence_lock = asyncio.Lock()
        self._sequence_cache: dict[str, int] = {}
        self._persist_details = False

    def set_persist_details(self, should_persist: bool) -> None:
        self._persist_details = should_persist

    def start(self) -> None:
        if self._worker is not None and not self._worker.done():
            return
        self._worker = asyncio.create_task(self._run(), name="llm-audit-queue")
        logger.info("LLM audit queue started")

    async def stop(self) -> None:
        if self._worker is None:
            return
        await self._queue.join()
        await self._queue.put(None)
        await self._worker
        self._worker = None
        logger.info("LLM audit queue stopped")

    async def enqueue(self, audit_log: LLMAuditLog) -> None:
        if self._worker is None or self._worker.done():
            self.start()
        await self._queue.put(persist_audit_details(audit_log, self._persist_details))

    async def next_call_sequence(self, session_id: str | None) -> int:
        if not session_id:
            return 1

        async with self._sequence_lock:
            current = self._sequence_cache.get(session_id)
            if current is None:
                current = await self._load_max_sequence(session_id)
            next_value = current + 1
            self._sequence_cache[session_id] = next_value
            return next_value

    async def _load_max_sequence(self, session_id: str) -> int:
        try:
            session = await create_session()
            async with session:
                result = await session.execute(
                    select(func.max(col(LLMAuditLog.call_sequence))).where(
                        col(LLMAuditLog.session_id) == session_id
                    )
                )
                return int(result.scalar_one_or_none() or 0)
        except Exception as exc:
            logger.error(f"failed to load audit call sequence: session_id={session_id}, error={exc}")
            return 0

    async def _run(self) -> None:
        while True:
            audit_log = await self._queue.get()
            try:
                if audit_log is None:
                    return
                await self._write(audit_log)
            except Exception as exc:
                logger.error(f"failed to write audit log: id={getattr(audit_log, 'id', None)}, error={exc}")
            finally:
                self._queue.task_done()

    async def _write(self, audit_log: LLMAuditLog) -> None:
        session = await create_session()
        async with session:
            session.add(audit_log)
            await session.commit()


audit_queue = AuditQueue()


def start_audit_queue() -> None:
    audit_queue.start()


async def stop_audit_queue() -> None:
    await audit_queue.stop()


def set_audit_details_persistence(should_persist: bool) -> None:
    audit_queue.set_persist_details(should_persist)


async def load_audit_details_persistence() -> None:
    session = await create_session()
    try:
        setting = await setting_repo.get_by_key(session, AUDIT_DETAILS_PERSISTENCE_SETTING_KEY)
        if setting is None:
            set_audit_details_persistence(False)
            return

        try:
            value = json.loads(setting.value)
        except json.JSONDecodeError:
            value = setting.value.strip().lower() in {"true", "1", "yes", "on"}
        set_audit_details_persistence(bool(value))
    finally:
        await session.close()


async def enqueue_audit_log(audit_log: LLMAuditLog) -> None:
    await audit_queue.enqueue(audit_log)


async def next_call_sequence(session_id: str | None) -> int:
    return await audit_queue.next_call_sequence(session_id)
