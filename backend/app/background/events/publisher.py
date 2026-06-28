"""Persist and publish background events."""

import json
import time
from datetime import UTC, datetime
from typing import Any, cast

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.background.jobs.models import BackgroundJob, BackgroundJobEvent
from app.background.jobs import repos as job_repo
from app.background.transport.base import BackgroundTransport
from app.background.transport.messages import BackgroundEventMessage


class BackgroundEventPublisher:
    """Writes job events and queues transport publish until commit succeeds."""

    def __init__(self, transport: BackgroundTransport | None = None):
        self._transport = transport

    async def publish(
        self,
        session: AsyncSession,
        *,
        job: BackgroundJob,
        job_id: str | None = None,
        job_type: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        event_type: str,
        payload: dict[str, Any] | None = None,
        item_id: str | None = None,
        item_type: str | None = None,
    ) -> BackgroundJobEvent:
        created_at = datetime.now(UTC)
        payload = payload or {}
        resolved_job_id = job_id or job.id
        if job_type is not None:
            resolved_job_type = job_type
        elif job_id is not None:
            resolved_job_type = "unknown"
        else:
            try:
                resolved_job_type = job.type or "unknown"
            except Exception:
                resolved_job_type = "unknown"
        resolved_subject_type = subject_type if subject_type is not None else job.subject_type
        resolved_subject_id = subject_id if subject_id is not None else job.subject_id
        sequence = await job_repo.next_event_sequence(session, resolved_job_id)
        event = await job_repo.create_event(
            session,
            BackgroundJobEvent(
                job_id=resolved_job_id,
                item_id=item_id,
                sequence=sequence,
                event_type=event_type,
                payload_json=json.dumps(payload, ensure_ascii=False),
                created_at=created_at,
            ),
        )
        if self._transport is not None:
            queue_committed_event(
                session,
                self._transport,
                BackgroundEventMessage(
                    type=event_type,
                    job_id=resolved_job_id,
                    job_type=resolved_job_type,
                    item_id=item_id,
                    item_type=item_type,
                    subject_type=resolved_subject_type,
                    subject_id=resolved_subject_id,
                    payload=payload,
                    created_at=created_at.isoformat(),
                    project_revision=time.time_ns(),
                ),
            )
        return event


_PENDING_EVENT_KEY = "background_event_messages"


def queue_committed_event(
    session: AsyncSession,
    transport: BackgroundTransport,
    message: BackgroundEventMessage,
) -> None:
    pending = session.info.setdefault(_PENDING_EVENT_KEY, [])
    if isinstance(pending, list):
        pending.append((transport, message))


async def publish_committed_events(session: AsyncSession) -> None:
    pending = session.info.pop(_PENDING_EVENT_KEY, [])
    if not isinstance(pending, list):
        return
    for item in pending:
        if not isinstance(item, tuple) or len(item) != 2:
            continue
        transport, message = item
        if isinstance(message, BackgroundEventMessage):
            try:
                await cast(BackgroundTransport, transport).publish_event(message)
            except Exception as exc:
                logger.bind(job_id=message.job_id, event_type=message.type).warning(
                    f"background event publish failed after commit: {exc}"
                )


def discard_queued_events(session: AsyncSession) -> None:
    session.info.pop(_PENDING_EVENT_KEY, None)
