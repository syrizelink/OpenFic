# -*- coding: utf-8 -*-
"""
Google Drive 自动同步的周期性调度任务。

独立于 background runtime，由应用 lifespan 启动/停止，每 60 秒检查一次。
"""

from __future__ import annotations

import asyncio

from loguru import logger

from app.google_drive import config as drive_config
from app.google_drive.service import run_periodic_sync_check


_scheduler_task: asyncio.Task[None] | None = None


async def start_drive_sync_scheduler() -> None:
    """启动定时同步任务。"""
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(
        _drive_sync_loop(), name="google-drive-sync-scheduler"
    )
    logger.info("Google Drive 自动同步调度已启动")


async def stop_drive_sync_scheduler() -> None:
    """停止定时同步任务。"""
    global _scheduler_task
    task = _scheduler_task
    _scheduler_task = None
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def _drive_sync_loop() -> None:
    while True:
        try:
            await run_periodic_sync_check()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f"Google Drive 同步循环异常: {exc}")
        await asyncio.sleep(drive_config.PERIODIC_CHECK_SECONDS)
