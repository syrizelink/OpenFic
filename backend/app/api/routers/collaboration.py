"""Authenticated Yjs WebSockets served by the existing FastAPI application."""

from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from loguru import logger
from pycrdt import create_awareness_message, create_sync_message
from sqlalchemy.ext.asyncio import AsyncSession

from app.collaboration.service import (
    Client,
    chapter_lock,
    control_message,
    document_record,
    hub,
    is_enabled,
    load_document,
    persist_document,
    room_for,
)
from app.core.errors import ConflictError
from app.storage.database import create_session, get_session

router = APIRouter(prefix="/collaboration", tags=["collaboration"])


@router.post("/chapters/{chapter_id}/session")
async def create_collaboration_session(
    chapter_id: str, session: Annotated[AsyncSession, Depends(get_session)]
) -> dict:
    if not await is_enabled(session):
        raise ConflictError("实验性协同编辑未开启")
    await hub.start()
    async with chapter_lock(chapter_id):
        record = await document_record(session, chapter_id)
        name = room_for(record)
        saved = await load_document(session, name)
        hub.get_room(name, saved)
        # Persist seed identities once, before clients can receive any content.
        if record.state is None:
            await persist_document(session, hub.snapshot(name), record_activity=False)
        await session.commit()
    return {"room": name}


@router.websocket("/chapters/{chapter_id}/{epoch}")
async def chapter_socket(websocket: WebSocket, chapter_id: str, epoch: str) -> None:
    name = f"{chapter_id}:{epoch}"
    session = await create_session()
    try:
        async with chapter_lock(chapter_id):
            if not await is_enabled(session) or hub.paused:
                await websocket.close(code=1008)
                return
            saved = await load_document(session, name)
            await hub.start()
            room = hub.get_room(name, saved)
    except (ConflictError, ValueError):
        await websocket.close(code=1008)
        return
    finally:
        await session.close()
    await websocket.accept()
    client = Client(websocket)
    room.clients.add(client)
    try:
        await client.send(create_sync_message(room.document))
        if room.awareness.states:
            await client.send(
                create_awareness_message(
                    room.awareness.encode_awareness_update(list(room.awareness.states))
                )
            )
        while True:
            await hub.handle_message(name, client, await websocket.receive_bytes())
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Collaboration connection failed: {}", exc)
        with suppress(RuntimeError, OSError):
            await client.send(control_message({"type": "error", "message": str(exc)}))
            await websocket.close(code=1011)
    finally:
        room.clients.discard(client)
        if client.awareness_ids:
            room.awareness.remove_awareness_states(list(client.awareness_ids), client)
            await hub.broadcast(
                room,
                create_awareness_message(
                    room.awareness.encode_awareness_update(list(client.awareness_ids))
                ),
            )
        if not room.clients:
            async with chapter_lock(chapter_id):
                if not room.clients and hub.rooms.get(name) is room:
                    hub.rooms.pop(name, None)
