"""Authenticated chapter sessions and same-origin Hocuspocus WebSocket proxy."""

import asyncio
from contextlib import suppress
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from app.collaboration.service import (
    chapter_lock,
    document_record,
    is_enabled,
    room_for,
    worker,
)
from app.core.errors import ConflictError
from app.storage.database import create_session, get_session

router = APIRouter(prefix="/collaboration", tags=["collaboration"])


@router.post("/chapters/{chapter_id}/session")
async def create_collaboration_session(
    chapter_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    if not await is_enabled(session):
        raise ConflictError("实验性协同编辑未开启")
    await worker.start()
    async with chapter_lock(chapter_id):
        record = await document_record(session, chapter_id)
        await session.commit()
    return {"room": room_for(record)}


@router.websocket("/chapters/{chapter_id}/{epoch}")
async def chapter_socket(websocket: WebSocket, chapter_id: str, epoch: str) -> None:
    session = await create_session()
    try:
        if not await is_enabled(session):
            await websocket.close(code=1008)
            return
        record = await document_record(session, chapter_id)
        if record.epoch != epoch:
            await websocket.close(code=1008)
            return
        await session.commit()
    except Exception:
        await websocket.close(code=1008)
        return
    finally:
        await session.close()
    await worker.start()
    room = f"{chapter_id}:{epoch}"
    query = urlencode({"room": room, "secret": worker.secret})
    await websocket.accept()
    try:
        async with connect(
            f"ws://127.0.0.1:{worker.port}/?{query}", max_size=8 * 1024 * 1024
        ) as upstream:

            async def client_to_server() -> None:
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    payload = message.get("bytes")
                    if payload is None:
                        payload = message["text"]
                    if isinstance(payload, (bytes, str)):
                        await upstream.send(payload)

            async def server_to_client() -> None:
                async for message in upstream:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            tasks = [
                asyncio.create_task(client_to_server()),
                asyncio.create_task(server_to_client()),
            ]
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except (WebSocketDisconnect, ConnectionClosed, OSError):
        pass
    finally:
        with suppress(RuntimeError, OSError):
            await websocket.close(code=1012)
