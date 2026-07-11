"""Database access for background jobs."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.background.jobs.models import BackgroundJob, BackgroundJobEvent, BackgroundJobItem
from app.background.jobs.states import JOB_STATUS_PENDING, JOB_STATUS_RUNNING, TERMINAL_STATUSES


async def create_job(session: AsyncSession, job: BackgroundJob) -> BackgroundJob:
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


async def get_job(session: AsyncSession, job_id: str) -> BackgroundJob | None:
    result = await session.execute(
        select(BackgroundJob).where(col(BackgroundJob.id) == job_id)
    )
    return result.scalar_one_or_none()


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
    query = select(BackgroundJob)
    if subject_type:
        query = query.where(col(BackgroundJob.subject_type) == subject_type)
    if subject_id:
        query = query.where(col(BackgroundJob.subject_id) == subject_id)
    if status:
        query = query.where(col(BackgroundJob.status) == status)
    if statuses:
        query = query.where(col(BackgroundJob.status).in_(statuses))
    if job_type:
        query = query.where(col(BackgroundJob.type) == job_type)
    if job_types:
        query = query.where(col(BackgroundJob.type).in_(job_types))
    query = query.order_by(col(BackgroundJob.created_at).desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_pending_jobs(session: AsyncSession, limit: int = 20) -> list[BackgroundJob]:
    now = datetime.now(UTC)
    result = await session.execute(
        select(BackgroundJob)
        .where(col(BackgroundJob.status) == JOB_STATUS_PENDING)
        .where(or_(col(BackgroundJob.next_run_at).is_(None), col(BackgroundJob.next_run_at) <= now))
        .order_by(col(BackgroundJob.created_at).asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def claim_job(
    session: AsyncSession,
    *,
    job_id: str,
    worker_id: str,
    lease_seconds: int,
) -> BackgroundJob | None:
    now = datetime.now(UTC)
    result = await session.execute(
        update(BackgroundJob)
        .where(col(BackgroundJob.id) == job_id)
        .where(col(BackgroundJob.status) == JOB_STATUS_PENDING)
        .where(or_(col(BackgroundJob.next_run_at).is_(None), col(BackgroundJob.next_run_at) <= now))
        .values(
            status=JOB_STATUS_RUNNING,
            locked_by=worker_id,
            locked_at=now,
            heartbeat_at=now,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            started_at=func.coalesce(col(BackgroundJob.started_at), now),
            updated_at=now,
            attempt_count=col(BackgroundJob.attempt_count) + 1,
        )
    )
    if getattr(result, "rowcount", 0) != 1:
        return None
    await session.flush()
    return await get_job(session, job_id)


async def save_job(session: AsyncSession, job: BackgroundJob) -> BackgroundJob:
    job.updated_at = datetime.now(UTC)
    session.add(job)
    await session.flush()
    await session.refresh(job)
    return job


async def next_event_sequence(session: AsyncSession, job_id: str) -> int:
    result = await session.execute(
        update(BackgroundJob)
        .where(col(BackgroundJob.id) == job_id)
        .values(
            event_sequence=col(BackgroundJob.event_sequence) + 1,
            updated_at=datetime.now(UTC),
        )
    )
    if getattr(result, "rowcount", 0) != 1:
        raise ValueError(f"后台任务不存在: {job_id}")
    await session.flush()
    job = await get_job(session, job_id)
    if job is None:
        raise ValueError(f"后台任务不存在: {job_id}")
    return job.event_sequence


async def list_expired_running_jobs(session: AsyncSession, *, limit: int = 50) -> list[BackgroundJob]:
    now = datetime.now(UTC)
    result = await session.execute(
        select(BackgroundJob)
        .where(col(BackgroundJob.status) == JOB_STATUS_RUNNING)
        .where(col(BackgroundJob.lease_expires_at).is_not(None))
        .where(col(BackgroundJob.lease_expires_at) < now)
        .order_by(col(BackgroundJob.lease_expires_at).asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_terminal_jobs_with_active_items(
    session: AsyncSession, *, limit: int = 50
) -> list[BackgroundJob]:
    result = await session.execute(
        select(BackgroundJob)
        .join(BackgroundJobItem)
        .where(col(BackgroundJob.status).in_(TERMINAL_STATUSES))
        .where(col(BackgroundJobItem.status).in_([JOB_STATUS_PENDING, JOB_STATUS_RUNNING]))
        .group_by(BackgroundJob.id)
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_event(
    session: AsyncSession,
    event: BackgroundJobEvent,
) -> BackgroundJobEvent:
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event


async def list_events(
    session: AsyncSession,
    *,
    job_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[BackgroundJobEvent]:
    result = await session.execute(
        select(BackgroundJobEvent)
        .where(col(BackgroundJobEvent.job_id) == job_id)
        .order_by(
            col(BackgroundJobEvent.sequence).asc(),
            col(BackgroundJobEvent.created_at).asc(),
            col(BackgroundJobEvent.id).asc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def create_item(session: AsyncSession, item: BackgroundJobItem) -> BackgroundJobItem:
    session.add(item)
    await session.flush()
    await session.refresh(item)
    return item


async def create_items(
    session: AsyncSession,
    items: list[BackgroundJobItem],
) -> list[BackgroundJobItem]:
    if not items:
        return []
    session.add_all(items)
    await session.flush()
    return items


async def list_items(
    session: AsyncSession,
    *,
    job_id: str,
) -> list[BackgroundJobItem]:
    result = await session.execute(
        select(BackgroundJobItem)
        .where(col(BackgroundJobItem.job_id) == job_id)
        .order_by(col(BackgroundJobItem.order_index).asc(), col(BackgroundJobItem.created_at).asc())
    )
    return list(result.scalars().all())


async def list_items_by_status(
    session: AsyncSession,
    *,
    job_id: str,
    statuses: set[str],
) -> list[BackgroundJobItem]:
    result = await session.execute(
        select(BackgroundJobItem)
        .where(col(BackgroundJobItem.job_id) == job_id)
        .where(col(BackgroundJobItem.status).in_(statuses))
        .order_by(col(BackgroundJobItem.order_index).asc(), col(BackgroundJobItem.created_at).asc())
    )
    return list(result.scalars().all())


async def list_items_by_ids(
    session: AsyncSession,
    *,
    item_ids: list[str],
) -> list[BackgroundJobItem]:
    if not item_ids:
        return []
    result = await session.execute(
        select(BackgroundJobItem).where(col(BackgroundJobItem.id).in_(item_ids))
    )
    return list(result.scalars().all())


async def save_item(session: AsyncSession, item: BackgroundJobItem) -> BackgroundJobItem:
    item.updated_at = datetime.now(UTC)
    session.add(item)
    await session.flush()
    await session.refresh(item)
    return item


async def mark_items_terminal_by_status(
    session: AsyncSession,
    *,
    job_id: str,
    statuses: set[str],
    terminal_status: str,
    error_json: str | None = None,
) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(BackgroundJobItem)
        .where(col(BackgroundJobItem.job_id) == job_id)
        .where(col(BackgroundJobItem.status).in_(statuses))
        .values(
            status=terminal_status,
            error_json=error_json,
            updated_at=now,
            finished_at=now,
        )
    )
    await session.flush()
