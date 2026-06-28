"""Watchdog for recovering stale background jobs."""

import asyncio
from contextlib import suppress

from loguru import logger

from app.background.events.publisher import BackgroundEventPublisher
from app.background.jobs import repos as job_repo
from app.background.jobs import service as job_service
from app.background.transport.base import BackgroundTransport
from app.settings import settings
from app.storage.database import create_session


class BackgroundWatchdog:
    """Periodically recovers jobs whose worker lease expired."""

    def __init__(self, *, transport: BackgroundTransport | None, interval_seconds: float) -> None:
        self.transport = transport
        self.interval_seconds = interval_seconds
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        logger.info("background watchdog started")
        while not self._stop_event.is_set():
            await self.run_once()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
        logger.info("background watchdog stopped")

    async def run_once(self) -> int:
        session = await create_session()
        publisher = BackgroundEventPublisher(self.transport)
        try:
            jobs = await job_repo.list_expired_running_jobs(session)
            for job in jobs:
                await job_service.recover_stale_job(
                    session,
                    publisher,
                    job,
                    reason="后台任务 worker lease 已过期",
                )
            await job_service.commit_and_notify(session)
            return len(jobs)
        except Exception:
            await session.rollback()
            raise
        finally:
            with suppress(Exception):
                await session.close()


def get_watchdog_interval_seconds() -> float:
    return max(float(settings.background_running_stale_seconds) / 2, 1.0)
