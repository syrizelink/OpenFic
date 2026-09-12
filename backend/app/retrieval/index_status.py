# -*- coding: utf-8 -*-
"""Koordinator pengiriman socket untuk status indeks.

Bertugas mengirim event `index:status` (per ruang proyek) dan `index:config`
(broadcast) ke frontend melalui Socket.IO setelah status indeks atau konfigurasi
indeks global berubah.

Pengiriman hanya dilakukan bila ada koneksi frontend, untuk menghindari efek samping
di lingkungan pengujian/tanpa koneksi.
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
    """Mendaftarkan hook after_commit sekali pakai, menjadwalkan coroutine setelah
    commit (hanya bila ada koneksi frontend).

    Proses pendaftaran bersifat best-effort: dilewati secara senyap bila session tidak
    mendukung event SQLAlchemy, agar efek samping pengiriman status indeks tidak
    mengganggu alur utama (misalnya penulisan bab).
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
    """Mengirim event index:status proyek tersebut setelah session saat ini commit."""
    _schedule_after_commit(session, lambda: _emit_status_for_project(project_id))


async def commit_and_emit_index_status(session: AsyncSession, project_id: str) -> None:
    """Commit one index progress snapshot and emit that exact committed state."""
    payload = await emit_project_index_status_payload(session, project_id)
    await session.commit()
    from app.socket import is_connected

    if is_connected():
        await _emit_status_for_project(project_id, payload=payload)


def schedule_emit_index_config(session: AsyncSession) -> None:
    """Menyiarkan event index:config setelah session saat ini commit (frontend memakai
    ini untuk menyegarkan status indeks)."""
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
