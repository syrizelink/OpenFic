"""Background worker loop."""

import asyncio
from contextlib import suppress

from loguru import logger

from app.background.events.publisher import BackgroundEventPublisher
from app.background.events.types import EVENT_JOB_STARTED
from app.background.jobs.constants import JOB_TYPE_SUMMARY_BATCH
from app.background.jobs import repos as job_repo
from app.background.jobs import service as job_service
from app.background.jobs.states import JOB_STATUS_CANCEL_REQUESTED, JOB_STATUS_RUNNING
from app.background.runtime.context import JobCancelledError, JobContext
from app.background.runtime.dispatcher import dispatch_job
from app.background.runtime.registry import get_job_registry
from app.background.transport.base import BackgroundTransport
from app.storage.database import create_session


class BackgroundWorker:
    """Consumes persisted jobs and runs registered handlers."""

    def __init__(
        self,
        *,
        worker_id: str,
        transport: BackgroundTransport,
        scan_interval_seconds: float,
    ) -> None:
        self.worker_id = worker_id
        self.transport = transport
        self.scan_interval_seconds = scan_interval_seconds
        self._stop_event = asyncio.Event()
        self._running_summary_batch_tasks: dict[str, asyncio.Task[dict | None]] = {}
        self._preempted_summary_batch_ids: set[str] = set()

    def stop(self) -> None:
        self._stop_event.set()

    def cancel_running_summary_batch(self, job_id: str) -> bool:
        task = self._running_summary_batch_tasks.get(job_id)
        if task is None or task.done():
            return False
        self._preempted_summary_batch_ids.add(job_id)
        task.cancel()
        return True

    async def run(self) -> None:
        logger.bind(worker_id=self.worker_id).info("Background worker started")
        while not self._stop_event.is_set():
            notification = await self.transport.receive_job(timeout_ms=500)
            if notification and notification.job_id:
                await self._run_job(notification.job_id)
                continue
            await self._run_pending_once()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.scan_interval_seconds
                )
        logger.bind(worker_id=self.worker_id).info("Background worker stopped")

    async def _run_pending_once(self) -> None:
        session = await create_session()
        try:
            jobs = await job_repo.list_pending_jobs(session, limit=5)
        finally:
            with suppress(Exception):
                await session.close()
        for job in jobs:
            if self._stop_event.is_set():
                return
            await self._run_job(job.id)

    async def _run_job(self, job_id: str) -> None:
        session = await create_session()
        publisher = BackgroundEventPublisher(self.transport)
        heartbeat_task: asyncio.Task[None] | None = None
        execution_task: asyncio.Task[dict | None] | None = None
        context: JobContext | None = None
        try:
            job = await job_repo.get_job(session, job_id)
            lease_seconds = job.timeout_seconds if job and job.timeout_seconds else 300
            job = await job_repo.claim_job(
                session,
                job_id=job_id,
                worker_id=self.worker_id,
                lease_seconds=lease_seconds,
            )
            if job is None:
                await session.rollback()
                return
            await publisher.publish(session, job=job, event_type=EVENT_JOB_STARTED)
            await job_service.commit_and_notify(session)
            heartbeat_task = asyncio.create_task(
                self._heartbeat_job(job.id, lease_seconds),
                name=f"background-heartbeat-{job.id}",
            )
            await session.close()
            session = await create_session()
            job = await job_repo.get_job(session, job.id)
            if job is None:
                await session.rollback()
                return

            context = JobContext(session=session, job=job, publisher=publisher)
            execution_task = asyncio.create_task(
                dispatch_job(context),
                name=f"background-job-{job.id}",
            )
            if job.type == JOB_TYPE_SUMMARY_BATCH:
                self._running_summary_batch_tasks[job.id] = execution_task
            if job.timeout_seconds is None:
                result = await execution_task
            else:
                result = await asyncio.wait_for(
                    execution_task,
                    timeout=job.timeout_seconds,
                )
            await context.refresh_job()
            if context.job.status == JOB_STATUS_RUNNING:
                await job_service.mark_succeeded(
                    context.session,
                    context.publisher,
                    context.job,
                    result=result or {},
                )
            await job_service.commit_and_notify(context.session)
        except asyncio.CancelledError:
            if job_id not in self._preempted_summary_batch_ids:
                raise
            logger.bind(job_id=job_id, worker_id=self.worker_id).info(
                "running summary batch interrupted by cancellation request"
            )
            await job_service.rollback_and_discard(context.session if context else session)
            await self._mark_cancelled_after_rollback(job_id, "用户停止摘要生成队列")
        except JobCancelledError as exc:
            logger.bind(job_id=job_id, worker_id=self.worker_id).info(
                f"background job cancelled: {exc}"
            )
            await job_service.rollback_and_discard(context.session if context else session)
            await self._mark_cancelled_after_rollback(job_id, str(exc))
        except TimeoutError as exc:
            logger.bind(job_id=job_id, worker_id=self.worker_id).warning(
                f"background job timed out: {exc}"
            )
            await job_service.rollback_and_discard(context.session if context else session)
            await self._mark_timeout_after_rollback(job_id, "后台任务执行超时")
        except Exception as exc:
            logger.bind(job_id=job_id, worker_id=self.worker_id).opt(exception=True).error(
                f"background job failed: {exc}"
            )
            await job_service.rollback_and_discard(context.session if context else session)
            await self._mark_failed_after_rollback(job_id, str(exc))
        finally:
            if execution_task is not None:
                self._running_summary_batch_tasks.pop(job_id, None)
            self._preempted_summary_batch_ids.discard(job_id)
            with suppress(asyncio.CancelledError):
                await self._stop_heartbeat(heartbeat_task)
            if context is not None and context.session is not session:
                with suppress(Exception):
                    await context.session.close()
            with suppress(Exception):
                await session.close()

    async def _heartbeat_job(self, job_id: str, lease_seconds: int) -> None:
        interval_seconds = max(min(float(lease_seconds) / 3, 30.0), 1.0)
        while not self._stop_event.is_set():
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval_seconds)
                return
            session = await create_session()
            try:
                job = await job_repo.get_job(session, job_id)
                if job is None or job.status != JOB_STATUS_RUNNING:
                    await session.rollback()
                    return
                await job_service.heartbeat_job(session, job, lease_seconds=lease_seconds)
                await session.commit()
            except Exception as exc:
                await session.rollback()
                logger.bind(job_id=job_id, worker_id=self.worker_id).warning(
                    f"background job heartbeat failed: {exc}"
                )
            finally:
                with suppress(Exception):
                    await session.close()

    async def _stop_heartbeat(self, task: asyncio.Task[None] | None) -> None:
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _mark_cancelled_after_rollback(self, job_id: str, reason: str) -> None:
        session = await create_session()
        publisher = BackgroundEventPublisher(self.transport)
        try:
            job = await job_repo.get_job(session, job_id)
            if job is not None:
                await self._run_lifecycle_hook(session, publisher, job, "cancelled", reason)
                await job_service.mark_cancelled(session, publisher, job, reason=reason)
                await job_service.commit_and_notify(session)
        finally:
            with suppress(Exception):
                await session.close()

    async def _mark_timeout_after_rollback(self, job_id: str, error_message: str) -> None:
        session = await create_session()
        publisher = BackgroundEventPublisher(self.transport)
        try:
            job = await job_repo.get_job(session, job_id)
            if job is not None:
                await self._run_lifecycle_hook(session, publisher, job, "timeout", error_message)
                await job_service.mark_timeout(session, publisher, job, error_message=error_message)
                await job_service.commit_and_notify(session)
        finally:
            with suppress(Exception):
                await session.close()

    async def _mark_failed_after_rollback(self, job_id: str, error_message: str) -> None:
        session = await create_session()
        publisher = BackgroundEventPublisher(self.transport)
        try:
            job = await job_repo.get_job(session, job_id)
            if job is not None:
                if job.status == JOB_STATUS_CANCEL_REQUESTED:
                    await self._run_lifecycle_hook(session, publisher, job, "cancelled", job.cancel_reason or error_message)
                    await job_service.mark_cancelled(session, publisher, job, reason=job.cancel_reason or error_message)
                elif job.attempt_count < job.max_attempts:
                    await job_service.schedule_retry(session, publisher, job, reason=error_message)
                else:
                    await self._run_lifecycle_hook(session, publisher, job, "failed", error_message)
                    await job_service.mark_failed(
                        session,
                        publisher,
                        job,
                        error_message=error_message,
                    )
                await job_service.commit_and_notify(session)
        finally:
            with suppress(Exception):
                await session.close()

    async def _run_lifecycle_hook(
        self,
        session,
        publisher: BackgroundEventPublisher,
        job,
        hook_name: str,
        reason: str,
    ) -> None:
        definition = get_job_registry().get(job.type)
        if definition is None:
            return
        hook = None
        if hook_name == "failed":
            hook = definition.on_failed
        elif hook_name == "timeout":
            hook = definition.on_timeout
        elif hook_name == "cancelled":
            hook = definition.on_cancelled
        if hook is None:
            return
        context = JobContext(session=session, job=job, publisher=publisher, definition=definition)
        await hook(context, reason)
