# -*- coding: utf-8 -*-
"""索引状态 socket 推送协调器。

负责在索引状态或全局索引配置变更后，通过 Socket.IO 向前端推送
`index:status`（按项目房间）与 `index:config`（广播）事件。

仅在存在前端连接时实际推送，避免在测试/无连接环境下产生副作用。
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger
from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.chapter_index import (
    ProjectIndexStatus,
    compute_project_index_status,
)
from app.socket import emit
from app.socket.handlers import background_project_room


INDEX_STATUS_EVENT = "index:status"
INDEX_CONFIG_EVENT = "index:config"


async def emit_project_index_status_payload(
    session: AsyncSession,
    project_id: str,
) -> dict[str, Any]:
    status = await compute_project_index_status(session, project_id=project_id)
    return status.to_payload()


async def _emit_status_for_project(
    project_id: str,
    *,
    payload: dict[str, Any] | None = None,
) -> None:
    from app.storage.database import create_session

    session = None
    try:
        if payload is None:
            session = await create_session()
            payload = await emit_project_index_status_payload(session, project_id)
        await emit(
            INDEX_STATUS_EVENT,
            payload,
            room=background_project_room(project_id),
        )
    except Exception as exc:
        logger.bind(project_id=project_id).warning(
            f"emit index:status failed: {exc}"
        )
    finally:
        if session is not None:
            await session.close()


async def _emit_index_config() -> None:
    try:
        await emit(INDEX_CONFIG_EVENT, {})
    except Exception as exc:
        logger.warning(f"emit index:config failed: {exc}")


def _schedule_after_commit(session: AsyncSession, coro_factory) -> None:
    """注册一次性 after_commit 钩子，在提交后调度协程（仅在有前端连接时）。

    注册过程为 best-effort：会话不具备 SQLAlchemy 事件支持时静默跳过，
    避免索引状态推送副作用影响主流程（如章节写入）。
    """
    from app.socket import is_connected

    try:
        sync_session = session.sync_session
    except Exception:
        return

    try:
        @sa_event.listens_for(sync_session, "after_commit", once=True)
        def _listener(_sync_session) -> None:  # noqa: ANN001
            if not is_connected():
                return
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            loop.create_task(coro_factory())
    except Exception as exc:
        logger.debug(f"schedule index status emit skipped: {exc}")


def schedule_emit_index_status(session: AsyncSession, project_id: str) -> None:
    """在当前 session 提交后推送该项目的 index:status 事件。"""
    _schedule_after_commit(session, lambda: _emit_status_for_project(project_id))


async def commit_and_emit_index_status(session: AsyncSession, project_id: str) -> None:
    """Commit one index progress snapshot and emit that exact committed state."""
    payload = await emit_project_index_status_payload(session, project_id)
    await session.commit()
    from app.socket import is_connected

    if is_connected():
        await _emit_status_for_project(project_id, payload=payload)


def schedule_emit_index_config(session: AsyncSession) -> None:
    """在当前 session 提交后广播 index:config 事件（前端据此刷新索引状态）。"""
    _schedule_after_commit(session, _emit_index_config)


__all__ = [
    "INDEX_STATUS_EVENT",
    "INDEX_CONFIG_EVENT",
    "ProjectIndexStatus",
    "emit_project_index_status_payload",
    "commit_and_emit_index_status",
    "schedule_emit_index_status",
    "schedule_emit_index_config",
]
