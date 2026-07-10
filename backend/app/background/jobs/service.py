"""Background job service API used by other modules."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.background.events.publisher import BackgroundEventPublisher
from app.background.events.publisher import discard_queued_events, publish_committed_events
from app.background.events.types import (
    EVENT_JOB_CANCEL_REQUESTED,
    EVENT_JOB_CANCELLED,
    EVENT_JOB_FAILED,
    EVENT_JOB_PROGRESS,
    EVENT_JOB_RECOVERED,
    EVENT_JOB_RETRY_SCHEDULED,
    EVENT_JOB_SKIPPED,
    EVENT_JOB_SUCCEEDED,
    EVENT_JOB_TIMEOUT,
)
from app.background.jobs import repos as job_repo
from app.background.jobs.models import BackgroundJob, BackgroundJobEvent, BackgroundJobItem
from app.background.jobs.states import (
    JOB_STATUS_CANCEL_REQUESTED,
    JOB_STATUS_CANCELLED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_SKIPPED,
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_TIMEOUT,
    TERMINAL_STATUSES,
)
from app.background.runtime.registry import get_job_registry
from app.background.transport.messages import JobNotification


_PENDING_NOTIFICATION_KEY = "background_job_notifications"


def parse_json_object(raw: str | None) -> dict[str, Any]:
    if raw is None:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _json(data: dict[str, Any] | None) -> str:
    return json.dumps(data or {}, ensure_ascii=False)


def _ensure_definition_registered(job_type: str) -> None:
    if get_job_registry().get(job_type) is not None:
        return
    from app.background.jobs.definitions import register_background_job_type

    register_background_job_type(job_type)


async def submit_job(
    session: AsyncSession,
    *,
    job_type: str,
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
    queue: str | None = None,
    max_attempts: int | None = None,
    timeout_seconds: int | None = None,
) -> BackgroundJob:
    """Create a persisted job and queue a post-commit runtime notification."""
    _ensure_definition_registered(job_type)
    definition = get_job_registry().get(job_type)
    if definition is None:
        raise ValueError(f"未注册的后台任务类型: {job_type}")

    definition.input_model.model_validate(payload)
    job = await job_repo.create_job(
        session,
        BackgroundJob(
            type=job_type,
            status=JOB_STATUS_PENDING,
            queue=queue or definition.default_queue,
            subject_type=subject_type,
            subject_id=subject_id,
            payload_json=_json(payload),
            context_json=_json(context),
            progress_json=_json({}),
            max_attempts=max_attempts or definition.default_max_attempts,
            timeout_seconds=timeout_seconds or definition.default_timeout_seconds,
        ),
    )
    _queue_submitted_job_notification(session, job.id)
    return job


def _queue_submitted_job_notification(session: AsyncSession, job_id: str) -> None:
    pending = session.info.setdefault(_PENDING_NOTIFICATION_KEY, [])
    if isinstance(pending, list) and job_id not in pending:
        pending.append(job_id)


async def notify_job_submitted(job_id: str) -> None:
    try:
        from app.background.runtime.supervisor import get_background_supervisor

        await get_background_supervisor().notify_job(JobNotification(job_id=job_id))
    except Exception as exc:
        logger.bind(job_id=job_id).warning(f"background job notify failed: {exc}")


async def notify_submitted_jobs(session: AsyncSession) -> None:
    pending = session.info.pop(_PENDING_NOTIFICATION_KEY, [])
    if not isinstance(pending, list):
        return
    for job_id in pending:
        if isinstance(job_id, str):
            try:
                await notify_job_submitted(job_id)
            except Exception as exc:
                logger.bind(job_id=job_id).warning(
                    f"background job notify failed after commit: {exc}"
                )


async def commit_and_notify(session: AsyncSession) -> None:
    await session.commit()
    await publish_committed_events(session)
    await notify_submitted_jobs(session)


async def rollback_and_discard(session: AsyncSession) -> None:
    await session.rollback()
    discard_queued_events(session)
    session.info.pop(_PENDING_NOTIFICATION_KEY, None)


async def get_job(session: AsyncSession, job_id: str) -> BackgroundJob | None:
    return await job_repo.get_job(session, job_id)


async def list_jobs(
    session: AsyncSession,
    *,
    subject_type: str | None = None,
    subject_id: str | None = None,
    status: str | None = None,
    statuses: set[str] | None = None,
    job_type: str | None = None,
    job_types: set[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[BackgroundJob]:
    return await job_repo.list_jobs(
        session,
        subject_type=subject_type,
        subject_id=subject_id,
        status=status,
        statuses=statuses,
        job_type=job_type,
        job_types=job_types,
        limit=limit,
        offset=offset,
    )


async def list_job_events(
    session: AsyncSession,
    *,
    job_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[BackgroundJobEvent]:
    return await job_repo.list_events(session, job_id=job_id, limit=limit, offset=offset)


async def list_job_items(session: AsyncSession, *, job_id: str) -> list[BackgroundJobItem]:
    return await job_repo.list_items(session, job_id=job_id)


async def list_job_items_by_ids(
    session: AsyncSession,
    *,
    item_ids: list[str],
) -> list[BackgroundJobItem]:
    return await job_repo.list_items_by_ids(session, item_ids=item_ids)


async def request_cancel(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
    *,
    reason: str | None = None,
) -> BackgroundJob:
    now = datetime.now(UTC)
    if job.status in TERMINAL_STATUSES:
        return job
    if job.status == JOB_STATUS_PENDING:
        return await mark_cancelled(session, publisher, job, reason=reason or "任务已取消")
    job.status = JOB_STATUS_CANCEL_REQUESTED
    job.cancel_requested_at = now
    job.cancel_reason = reason
    await job_repo.save_job(session, job)
    await append_event(
        session,
        publisher,
        job,
        event_type=EVENT_JOB_CANCEL_REQUESTED,
        payload={"reason": reason},
    )
    return job


async def cancel_job(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
    *,
    reason: str | None = None,
) -> BackgroundJob:
    """取消任务；等待中的任务同步运行取消清理钩子。"""
    was_pending = job.status == JOB_STATUS_PENDING
    job = await request_cancel(session, publisher, job, reason=reason)
    if not was_pending or job.status != JOB_STATUS_CANCELLED:
        return job

    definition = get_job_registry().get(job.type)
    if definition is None or definition.on_cancelled is None:
        return job

    from app.background.runtime.context import JobContext

    context = JobContext(session=session, job=job, publisher=publisher, definition=definition)
    await definition.on_cancelled(context, job.cancel_reason or "任务已取消")
    return job


async def append_event(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
    *,
    job_id: str | None = None,
    job_type: str | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
    event_type: str,
    payload: dict[str, Any] | None = None,
    item_id: str | None = None,
    item_type: str | None = None,
) -> BackgroundJobEvent:
    return await publisher.publish(
        session,
        job=job,
        job_id=job_id,
        job_type=job_type,
        subject_type=subject_type,
        subject_id=subject_id,
        event_type=event_type,
        payload=payload,
        item_id=item_id,
        item_type=item_type,
    )


async def update_progress(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
    *,
    current: int,
    total: int | None = None,
    message: str | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> BackgroundJob:
    progress = {
        "current": max(current, 0),
        "total": total,
        "message": message,
    }
    payload = {**progress, **(extra_payload or {})}
    job.progress_json = _json(payload)
    await job_repo.save_job(session, job)
    await append_event(session, publisher, job, event_type=EVENT_JOB_PROGRESS, payload=payload)
    return job


async def heartbeat_job(
    session: AsyncSession,
    job: BackgroundJob,
    *,
    lease_seconds: int,
) -> BackgroundJob:
    now = datetime.now(UTC)
    job.heartbeat_at = now
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    return await job_repo.save_job(session, job)


async def mark_succeeded(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
    *,
    result: dict[str, Any] | None = None,
) -> BackgroundJob:
    now = datetime.now(UTC)
    job.status = JOB_STATUS_SUCCEEDED
    job.result_json = _json(result)
    job.finished_at = now
    _clear_lock(job)
    await job_repo.save_job(session, job)
    await append_event(session, publisher, job, event_type=EVENT_JOB_SUCCEEDED, payload=result or {})
    return job


async def mark_failed(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
    *,
    error_message: str,
) -> BackgroundJob:
    now = datetime.now(UTC)
    error = {"message": error_message}
    job.status = JOB_STATUS_FAILED
    job.error_json = _json(error)
    job.finished_at = now
    _clear_lock(job)
    await job_repo.save_job(session, job)
    await append_event(session, publisher, job, event_type=EVENT_JOB_FAILED, payload=error)
    return job


async def mark_timeout(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
    *,
    error_message: str,
) -> BackgroundJob:
    now = datetime.now(UTC)
    error = {"message": error_message}
    job.status = JOB_STATUS_TIMEOUT
    job.error_json = _json(error)
    job.finished_at = now
    _clear_lock(job)
    await job_repo.save_job(session, job)
    await append_event(session, publisher, job, event_type=EVENT_JOB_TIMEOUT, payload=error)
    return job


async def mark_cancelled(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
    *,
    reason: str,
) -> BackgroundJob:
    now = datetime.now(UTC)
    error = {"message": reason}
    job.status = JOB_STATUS_CANCELLED
    job.error_json = _json(error)
    job.cancel_reason = job.cancel_reason or reason
    job.finished_at = now
    _clear_lock(job)
    await job_repo.save_job(session, job)
    await append_event(session, publisher, job, event_type=EVENT_JOB_CANCELLED, payload=error)
    return job


async def schedule_retry(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
    *,
    reason: str,
) -> BackgroundJob:
    job.status = JOB_STATUS_PENDING
    job.error_json = _json({"message": reason})
    job.finished_at = None
    job.next_run_at = datetime.now(UTC)
    _clear_lock(job)
    await job_repo.save_job(session, job)
    await append_event(
        session,
        publisher,
        job,
        event_type=EVENT_JOB_RETRY_SCHEDULED,
        payload={"reason": reason, "attempt_count": job.attempt_count},
    )
    return job


async def recover_stale_job(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
    *,
    reason: str,
) -> BackgroundJob:
    if job.attempt_count < job.max_attempts:
        job.status = JOB_STATUS_PENDING
        job.next_run_at = datetime.now(UTC)
        _clear_lock(job)
        await job_repo.save_job(session, job)
        await append_event(
            session,
            publisher,
            job,
            event_type=EVENT_JOB_RECOVERED,
            payload={"reason": reason, "attempt_count": job.attempt_count},
        )
        return job
    definition = get_job_registry().get(job.type)
    if definition is not None and definition.on_timeout is not None:
        from app.background.runtime.context import JobContext

        context = JobContext(session=session, job=job, publisher=publisher, definition=definition)
        await definition.on_timeout(context, reason)
    return await mark_timeout(session, publisher, job, error_message=reason)


_ORPHAN_HOOK_BY_STATUS = {
    JOB_STATUS_TIMEOUT: "on_timeout",
    JOB_STATUS_FAILED: "on_failed",
    JOB_STATUS_CANCELLED: "on_cancelled",
}


async def finalize_orphan_job_items(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
) -> None:
    """Re-run the terminal lifecycle hook for a job that reached a terminal state
    while some of its items were still pending or running (e.g. after an unclean
    restart before the watchdog timeout-hook fix)."""
    definition = get_job_registry().get(job.type)
    if definition is None:
        return
    hook_name = _ORPHAN_HOOK_BY_STATUS.get(job.status, "on_failed")
    hook = getattr(definition, hook_name, None) or definition.on_failed
    if hook is None:
        return
    from app.background.runtime.context import JobContext

    context = JobContext(session=session, job=job, publisher=publisher, definition=definition)
    await hook(context, f"启动恢复：任务已 {job.status} 但仍存在未完成的子项")


async def mark_skipped(
    session: AsyncSession,
    publisher: BackgroundEventPublisher,
    job: BackgroundJob,
    *,
    reason: str,
) -> BackgroundJob:
    now = datetime.now(UTC)
    payload = {"reason": reason}
    job.status = JOB_STATUS_SKIPPED
    job.error_json = _json({"message": reason})
    job.finished_at = now
    _clear_lock(job)
    await job_repo.save_job(session, job)
    await append_event(session, publisher, job, event_type=EVENT_JOB_SKIPPED, payload=payload)
    return job


async def create_item(
    session: AsyncSession,
    *,
    job_id: str,
    item_key: str,
    item_type: str,
    payload: dict[str, Any] | None = None,
    order_index: int = 0,
) -> BackgroundJobItem:
    return await job_repo.create_item(
        session,
        BackgroundJobItem(
            job_id=job_id,
            item_key=item_key,
            type=item_type,
            payload_json=_json(payload),
            order_index=order_index,
        ),
    )


async def update_item_progress(
    session: AsyncSession,
    item: BackgroundJobItem,
    *,
    progress: dict[str, Any],
) -> BackgroundJobItem:
    item.progress_json = _json(progress)
    return await job_repo.save_item(session, item)


def _clear_lock(job: BackgroundJob) -> None:
    job.locked_by = None
    job.locked_at = None
    job.heartbeat_at = None
    job.lease_expires_at = None
