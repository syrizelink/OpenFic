"""pyzmq transport implementation for local background runtime messaging."""

from typing import Any

import zmq
import zmq.asyncio
from loguru import logger

from app.background.transport.base import BackgroundTransport
from app.background.transport.messages import BackgroundEventMessage, JobNotification


class ZmqBackgroundTransport(BackgroundTransport):
    """Local pyzmq transport for job notifications and events."""

    def __init__(self, job_endpoint: str, event_endpoint: str):
        self.job_endpoint = job_endpoint
        self.event_endpoint = event_endpoint
        self._context: zmq.asyncio.Context | None = None
        self._job_push: zmq.asyncio.Socket | None = None
        self._job_pull: zmq.asyncio.Socket | None = None
        self._event_pub: zmq.asyncio.Socket | None = None
        self._event_sub: zmq.asyncio.Socket | None = None

    async def start(self) -> None:
        if self._context is not None:
            return

        context = zmq.asyncio.Context()
        job_pull = context.socket(zmq.PULL)
        job_push = context.socket(zmq.PUSH)
        event_pub = context.socket(zmq.PUB)
        event_sub = context.socket(zmq.SUB)

        try:
            job_pull.bind(self.job_endpoint)
            job_push.connect(self.job_endpoint)
            event_pub.bind(self.event_endpoint)
            event_sub.connect(self.event_endpoint)
            event_sub.setsockopt_string(zmq.SUBSCRIBE, "")
        except Exception:
            for socket in (job_pull, job_push, event_pub, event_sub):
                socket.close(linger=0)
            context.term()
            raise

        self._context = context
        self._job_pull = job_pull
        self._job_push = job_push
        self._event_pub = event_pub
        self._event_sub = event_sub
        logger.info("Background ZMQ transport started")

    async def stop(self) -> None:
        sockets = [self._job_push, self._job_pull, self._event_pub, self._event_sub]
        for socket in sockets:
            if socket is not None:
                socket.close(linger=0)
        if self._context is not None:
            self._context.term()
        self._context = None
        self._job_push = None
        self._job_pull = None
        self._event_pub = None
        self._event_sub = None

    async def notify_job(self, message: JobNotification) -> None:
        if self._job_push is None:
            return
        await self._job_push.send_json({"job_id": message.job_id})

    async def receive_job(self, timeout_ms: int) -> JobNotification | None:
        if self._job_pull is None:
            return None
        if not await self._poll(self._job_pull, timeout_ms):
            return None
        payload = await self._job_pull.recv_json()
        job_id = str(payload.get("job_id") or "")
        return JobNotification(job_id=job_id) if job_id else None

    async def publish_event(self, message: BackgroundEventMessage) -> None:
        if self._event_pub is None:
            return
        await self._event_pub.send_json(
            {
                "type": message.type,
                "job_id": message.job_id,
                "job_type": message.job_type,
                "item_id": message.item_id,
                "item_type": message.item_type,
                "subject_type": message.subject_type,
                "subject_id": message.subject_id,
                "payload": message.payload,
                "created_at": message.created_at,
                "project_revision": message.project_revision,
            }
        )

    async def receive_event(self, timeout_ms: int) -> BackgroundEventMessage | None:
        if self._event_sub is None:
            return None
        if not await self._poll(self._event_sub, timeout_ms):
            return None
        payload: dict[str, Any] = await self._event_sub.recv_json()
        event_payload_raw = payload.get("payload")
        event_payload: dict[str, Any] = (
            event_payload_raw if isinstance(event_payload_raw, dict) else {}
        )
        return BackgroundEventMessage(
            type=str(payload.get("type") or ""),
            job_id=str(payload.get("job_id") or ""),
            job_type=str(payload.get("job_type") or "unknown"),
            item_id=str(payload.get("item_id")) if payload.get("item_id") else None,
            item_type=str(payload.get("item_type")) if payload.get("item_type") else None,
            subject_type=payload.get("subject_type"),
            subject_id=payload.get("subject_id"),
            payload=event_payload,
            created_at=str(payload.get("created_at") or ""),
            project_revision=(
                int(payload["project_revision"])
                if isinstance(payload.get("project_revision"), int)
                else None
            ),
        )

    async def _poll(self, socket: zmq.asyncio.Socket, timeout_ms: int) -> bool:
        events = await socket.poll(timeout=timeout_ms)
        return bool(events)
