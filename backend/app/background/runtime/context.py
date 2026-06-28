"""Runtime context passed to background job handlers."""

import json
from dataclasses import dataclass
from contextlib import suppress
from typing import Any, Awaitable, Callable, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.background.events.publisher import BackgroundEventPublisher
from app.background.jobs.base import JobDefinition
from app.background.jobs.models import BackgroundJob
from app.background.jobs import service as job_service
from app.background.jobs.states import JOB_STATUS_CANCEL_REQUESTED
from app.storage.database import create_session


T = TypeVar("T")


class JobCancelledError(RuntimeError):
    """Raised when a job observes a cancellation request."""


@dataclass
class JobContext:
    """Execution context for one background job."""

    session: AsyncSession
    job: BackgroundJob
    publisher: BackgroundEventPublisher
    definition: JobDefinition | None = None
    payload: BaseModel | None = None

    def __post_init__(self) -> None:
        self.job_id = self.job.id
        self.job_type = self.job.type
        self.subject_type = self.job.subject_type
        self.subject_id = self.job.subject_id
        self.payload_json = self.job.payload_json
        self.context_json = self.job.context_json
        self.timeout_seconds = self.job.timeout_seconds

    @property
    def input(self) -> dict[str, Any]:
        return self._json_object(self.payload_json)

    @property
    def data(self) -> dict[str, Any]:
        return self.input

    @property
    def metadata(self) -> dict[str, Any]:
        return self._json_object(self.context_json)

    @property
    def typed_payload(self) -> BaseModel:
        if self.payload is None:
            raise RuntimeError("后台任务 payload 尚未校验")
        return self.payload

    async def progress(
        self,
        current: int,
        *,
        total: int | None = None,
        message: str | None = None,
    ) -> None:
        self.job = await job_service.update_progress(
            self.session,
            self.publisher,
            self.job,
            current=current,
            total=total,
            message=message,
        )
        await self.commit()

    async def heartbeat(self) -> None:
        lease_seconds = self.timeout_seconds or 300
        self.job = await job_service.heartbeat_job(
            self.session,
            self.job,
            lease_seconds=lease_seconds,
        )
        await self.commit()

    async def check_cancelled(self) -> None:
        session = await create_session()
        try:
            job = await job_service.get_job(session, self.job_id)
            if job is None:
                raise RuntimeError(f"后台任务不存在: {self.job_id}")
            if job.status == JOB_STATUS_CANCEL_REQUESTED or job.cancel_requested_at:
                raise JobCancelledError(job.cancel_reason or "后台任务已请求取消")
        finally:
            with suppress(Exception):
                await session.close()

    async def commit(self) -> None:
        await job_service.commit_and_notify(self.session)
        await self.session.refresh(self.job)
        self._sync_job_snapshot()

    async def run_in_transaction(
        self,
        callback: Callable[[AsyncSession, BackgroundJob], Awaitable[T]],
    ) -> T:
        result = await callback(self.session, self.job)
        await self.commit()
        return result

    async def with_short_session(
        self,
        callback: Callable[[AsyncSession, BackgroundJob], Awaitable[T]],
    ) -> T:
        with suppress(Exception):
            await self.session.rollback()
        with suppress(Exception):
            await self.session.close()
        session = await create_session()
        self.session = session
        job = await job_service.get_job(session, self.job_id)
        if job is None:
            raise RuntimeError(f"后台任务不存在: {self.job_id}")
        self.job = job
        self._sync_job_snapshot()
        try:
            result = await callback(session, job)
            await self.commit()
            return result
        except Exception:
            await job_service.rollback_and_discard(session)
            raise

    async def refresh_job(self) -> None:
        job = await job_service.get_job(self.session, self.job_id)
        if job is None:
            raise RuntimeError(f"后台任务不存在: {self.job_id}")
        self.job = job
        self._sync_job_snapshot()

    def _sync_job_snapshot(self) -> None:
        self.job_id = self.job.id
        self.job_type = self.job.type
        self.subject_type = self.job.subject_type
        self.subject_id = self.job.subject_id
        self.payload_json = self.job.payload_json
        self.context_json = self.job.context_json
        self.timeout_seconds = self.job.timeout_seconds

    def _json_object(self, raw: str | None) -> dict[str, Any]:
        if raw is None:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}
