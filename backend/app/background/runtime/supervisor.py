"""Background runtime supervisor and application lifecycle hooks."""

import asyncio
import uuid
from contextlib import suppress
from typing import Any

from loguru import logger

from app.background.events.publisher import BackgroundEventPublisher
from app.background.jobs import repos as job_repo
from app.background.jobs import service as job_service
from app.background.runtime.worker import BackgroundWorker
from app.background.runtime.watchdog import BackgroundWatchdog, get_watchdog_interval_seconds
from app.background.transport.messages import BackgroundEventMessage, JobNotification
from app.background.transport.zmq import ZmqBackgroundTransport
from app.socket import emit
from app.socket.handlers import agent_session_room, background_project_room
from app.settings import settings
from app.storage.database import create_session


class BackgroundSupervisor:
    """Owns background transport, worker, and event bridge lifecycles."""

    def __init__(self) -> None:
        self._transport: ZmqBackgroundTransport | None = None
        self._workers: list[BackgroundWorker] = []
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._watchdog: BackgroundWatchdog | None = None
        self._watchdog_task: asyncio.Task[None] | None = None
        self._event_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._worker_id = settings.background_worker_id or f"worker-{uuid.uuid4().hex[:8]}"

    async def start(self) -> None:
        if not settings.background_enabled or self._transport is not None:
            return
        from app.background.jobs.definitions import register_all_background_jobs

        register_all_background_jobs()
        self._stop_event.clear()
        self._transport = ZmqBackgroundTransport(
            settings.background_zmq_job_endpoint,
            settings.background_zmq_event_endpoint,
        )
        await self._transport.start()
        await self._recover_stale_jobs()
        self._event_task = asyncio.create_task(self._run_event_bridge())
        if settings.background_worker_enabled:
            worker_count = max(settings.background_worker_concurrency, 1)
            for index in range(worker_count):
                worker = BackgroundWorker(
                    worker_id=f"{self._worker_id}-{index + 1}",
                    transport=self._transport,
                    scan_interval_seconds=settings.background_job_scan_interval_seconds,
                )
                self._workers.append(worker)
                self._worker_tasks.append(asyncio.create_task(worker.run()))
            self._watchdog = BackgroundWatchdog(
                transport=self._transport,
                interval_seconds=get_watchdog_interval_seconds(),
            )
            self._watchdog_task = asyncio.create_task(self._watchdog.run())
        logger.info("Background supervisor started")

    async def stop(self) -> None:
        self._stop_event.set()
        for worker in self._workers:
            worker.stop()
        if self._watchdog is not None:
            self._watchdog.stop()
        tasks = [
            *self._worker_tasks,
            *[task for task in (self._watchdog_task, self._event_task) if task is not None],
        ]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        if self._transport is not None:
            await self._transport.stop()
        self._transport = None
        self._workers = []
        self._worker_tasks = []
        self._watchdog = None
        self._watchdog_task = None
        self._event_task = None
        logger.info("background supervisor stopped")

    async def notify_job(self, message: JobNotification) -> None:
        if self._transport is None:
            return
        await self._transport.notify_job(message)

    def create_event_publisher(self) -> BackgroundEventPublisher:
        return BackgroundEventPublisher(self._transport)

    async def _run_event_bridge(self) -> None:
        assert self._transport is not None
        while not self._stop_event.is_set():
            message = await self._transport.receive_event(timeout_ms=500)
            if message is None:
                continue
            await self._emit_socket_background_event(message)

    async def _recover_stale_jobs(self) -> None:
        assert self._transport is not None
        watchdog = BackgroundWatchdog(
            transport=self._transport,
            interval_seconds=get_watchdog_interval_seconds(),
        )
        count = await watchdog.run_once()
        if count:
            logger.warning(f"recovered {count} stale background jobs")
        orphan_count = await self._finalize_orphan_job_items()
        if orphan_count:
            logger.warning(f"finalized orphan items for {orphan_count} terminal background jobs")

    async def _finalize_orphan_job_items(self) -> int:
        assert self._transport is not None
        session = await create_session()
        publisher = BackgroundEventPublisher(self._transport)
        try:
            jobs = await job_repo.list_terminal_jobs_with_active_items(session)
            for job in jobs:
                await job_service.finalize_orphan_job_items(session, publisher, job)
            await job_service.commit_and_notify(session)
            return len(jobs)
        except Exception:
            await session.rollback()
            raise
        finally:
            with suppress(Exception):
                await session.close()

    def _resolve_project_id(self, message: BackgroundEventMessage) -> str | None:
        project_id = message.payload.get("project_id")
        if isinstance(project_id, str) and project_id:
            return project_id
        if message.subject_type == "project" and isinstance(message.subject_id, str) and message.subject_id:
            return message.subject_id
        return None

    def _socket_payload(self, message: BackgroundEventMessage) -> dict[str, Any]:
        payload = {
            "type": message.type,
            "job_type": message.job_type,
            "job_id": message.job_id,
            "item_id": message.item_id,
            "item_type": message.item_type,
            "subject_type": message.subject_type,
            "subject_id": message.subject_id,
            "payload": message.payload,
            "created_at": message.created_at,
            "project_revision": message.project_revision,
            **self._flatten_known_event(message),
        }
        project_id = self._resolve_project_id(message)
        if project_id is not None:
            payload["project_id"] = project_id
        return payload

    async def _emit_socket_background_event(self, message: BackgroundEventMessage) -> None:
        project_id = self._resolve_project_id(message)
        payload = self._socket_payload(message)
        if project_id is not None:
            await emit(
                "background:event",
                payload,
                room=background_project_room(project_id),
            )
        if message.type == "task_title_updated":
            agent_session_id = message.payload.get("agent_session_id")
            if isinstance(agent_session_id, str) and agent_session_id:
                await emit(
                    "agent:task_title_updated",
                    {
                        "session_id": agent_session_id,
                        "task_id": message.payload.get("task_id"),
                        "project_id": project_id,
                        "chapter_id": message.payload.get("chapter_id"),
                        "title": message.payload.get("title"),
                        "updated_at": message.payload.get("updated_at"),
                    },
                    room=agent_session_room(agent_session_id),
                )

    def _flatten_known_event(self, message: BackgroundEventMessage) -> dict[str, Any]:
        if message.type == "task_title_updated":
            return {
                "task_id": message.payload.get("task_id"),
                "project_id": message.payload.get("project_id"),
                "chapter_id": message.payload.get("chapter_id"),
                "agent_session_id": message.payload.get("agent_session_id"),
                "title": message.payload.get("title"),
                "updated_at": message.payload.get("updated_at"),
            }
        return {}


_supervisor = BackgroundSupervisor()


def get_background_supervisor() -> BackgroundSupervisor:
    return _supervisor


async def start_background_runtime() -> None:
    await _supervisor.start()


async def stop_background_runtime() -> None:
    await _supervisor.stop()
