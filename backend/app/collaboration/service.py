"""Yjs-compatible collaboration and transactional persistence inside FastAPI."""

import asyncio
import base64
from contextlib import AsyncExitStack, asynccontextmanager
from difflib import SequenceMatcher
import json
import os
from typing import Any
from dataclasses import dataclass, field

from fastapi import WebSocket
from pycrdt import (
    Doc,
    Awareness,
    create_update_message,
    handle_sync_message,
    read_message,
    write_message,
    create_awareness_message,
)

from app.collaboration.document import (
    new_document,
    clone_document,
    text_of,
    replace_exact,
    restore_ranges,
)

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.core.errors import ConflictError, NotFoundError
from app.storage.models.chapter_collaboration import ChapterCollaboration
from app.storage.models.setting import Setting
from app.storage.repos import chapter_repo

SETTING_KEY = "human_ai_collaboration"
_locks: dict[str, asyncio.Lock] = {}


def chapter_lock(chapter_id: str) -> asyncio.Lock:
    return _locks.setdefault(chapter_id, asyncio.Lock())


async def is_enabled(session: AsyncSession) -> bool:
    value = await session.scalar(
        select(col(Setting.value)).where(col(Setting.key) == SETTING_KEY)
    )
    return value == "true"


async def document_record(
    session: AsyncSession, chapter_id: str
) -> ChapterCollaboration:
    chapter = await chapter_repo.get_by_id(session, chapter_id)
    if chapter is None:
        raise NotFoundError("章节不存在")
    record = await session.get(ChapterCollaboration, chapter_id)
    if record is None:
        record = ChapterCollaboration(chapter_id=chapter_id)
        session.add(record)
        await session.flush()
    return record


def room_for(record: ChapterCollaboration) -> str:
    return f"{record.chapter_id}:{record.epoch}"


async def load_document(session: AsyncSession, room: str) -> dict:
    chapter_id, epoch = room.split(":", 1)
    record = await session.get(ChapterCollaboration, chapter_id)
    chapter = await chapter_repo.get_by_id(session, chapter_id)
    if record is None or record.epoch != epoch or chapter is None:
        raise ConflictError("协同文档已失效，请重新打开章节")
    return {
        "state": base64.b64encode(record.state).decode() if record.state else None,
        "content": chapter.content,
        "version": record.version,
    }


async def persist_document(
    session: AsyncSession, data: dict, *, record_activity: bool = True
) -> None:
    from app.storage.services import chapter_service

    chapter_id, epoch = data["room"].split(":", 1)
    record = await session.get(ChapterCollaboration, chapter_id, populate_existing=True)
    if record is None or record.epoch != epoch:
        raise ConflictError("协同文档已失效")
    if data["version"] <= record.version and record.state is not None:
        return
    state = base64.b64decode(data["state"], validate=True)
    if len(state) > 8 * 1024 * 1024:
        raise ValueError("协同文档状态过大")
    record.state = state
    record.version = data["version"]
    session.add(record)
    session.info["collaboration_write"] = True
    try:
        await chapter_service.update_chapter(
            session,
            chapter_id,
            content=data["content"],
            record_activity=record_activity,
        )
        await session.flush()
    finally:
        session.info.pop("collaboration_write", None)


@dataclass(eq=False)
class Client:
    socket: WebSocket
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    awareness_ids: set[int] = field(default_factory=set)

    async def send(self, message: bytes) -> None:
        async with self.send_lock:
            await asyncio.wait_for(self.socket.send_bytes(message), 5)


@dataclass
class Room:
    document: Doc
    version: int
    clients: set[Client] = field(default_factory=set)
    awareness: Awareness = field(init=False)

    def __post_init__(self) -> None:
        self.awareness = Awareness(self.document)
        self.awareness.set_local_state(None)


def control_message(message: dict) -> bytes:
    return b"\x04" + write_message(json.dumps(message, ensure_ascii=False).encode())


class CollaborationHub:
    """Own documents inside FastAPI; no subprocess, extra listener or external service."""

    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self.paused = False
        self.started = False
        self._lease = None

    async def start(self) -> None:
        if self.started:
            return
        from app.settings import BACKEND_DATA_DIR

        BACKEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
        lease = (BACKEND_DATA_DIR / ".collaboration.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                lease.write(b"0")
                lease.flush()
                lease.seek(0)
                msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            lease.close()
            raise ConflictError("协同编辑只支持单个后端进程") from exc
        self._lease = lease
        self.started = True
        self.paused = False

    async def resume(self) -> None:
        await self.start()
        self.paused = False

    async def pause(self) -> None:
        self.paused = True
        # Accepted updates are committed before broadcasting, so no flush is needed.
        for room in list(self.rooms.values()):
            for client in list(room.clients):
                try:
                    await client.socket.close(code=1012)
                except (RuntimeError, OSError):
                    pass
            room.clients.clear()
        self.rooms.clear()

    async def stop(self) -> None:
        await self.pause()
        if self._lease is not None:
            self._lease.close()
            self._lease = None
        self.started = False

    def get_room(self, name: str, saved: dict) -> Room:
        if name not in self.rooms:
            state = base64.b64decode(saved["state"]) if saved["state"] else None
            self.rooms[name] = Room(
                new_document(saved["content"], state), saved["version"]
            )
        return self.rooms[name]

    def snapshot(
        self, name: str, document: Doc | None = None, version: int | None = None
    ) -> dict:
        room = self.rooms[name]
        document = document if document is not None else room.document
        return {
            "room": name,
            "state": base64.b64encode(document.get_update()).decode(),
            "content": text_of(document),
            "version": room.version if version is None else version,
        }

    def prepare(
        self,
        name: str,
        saved: dict,
        *,
        old_content: str | None = None,
        new_content: str | None = None,
        replace_all: bool = False,
        edits: list[dict] | None = None,
    ) -> dict:
        if self.paused:
            raise ConflictError("协同编辑已暂停")
        room = self.get_room(name, saved)
        candidate = clone_document(room.document)
        before = text_of(candidate)
        if edits is not None:
            restore_ranges(candidate, edits)
        elif old_content is not None and new_content is not None:
            replace_exact(candidate, old_content, new_content, replace_all)
        else:
            raise ValueError("缺少章节编辑内容")
        room.version += 1
        return {**self.snapshot(name, candidate), "before": before}

    async def broadcast(self, room: Room, message: bytes) -> None:
        async def deliver(client: Client) -> None:
            try:
                await client.send(message)
            except Exception:
                room.clients.discard(client)
                try:
                    await client.socket.close(code=1011)
                except (RuntimeError, OSError):
                    pass

        await asyncio.gather(*(deliver(client) for client in list(room.clients)))

    async def acknowledge(self, room: Room, client: Client | None = None) -> None:
        message = control_message(
            {
                "type": "saved",
                "content": text_of(room.document),
                "vector": list(room.document.get_state()),
            }
        )
        if client is not None:
            await client.send(message)
        else:
            await self.broadcast(room, message)

    async def publish(self, data: dict) -> None:
        room = self.rooms.get(data["room"])
        if room is None:
            # New connections load the committed state from the business database.
            return
        candidate = new_document(state=base64.b64decode(data["state"]))
        update = candidate.get_update(room.document.get_state())
        room.document.apply_update(update)
        room.version = max(room.version, data["version"])
        await self.broadcast(room, create_update_message(update))
        await self.acknowledge(room)

    async def evict(self, name: str) -> None:
        room = self.rooms.pop(name, None)
        if room is not None:
            for client in list(room.clients):
                try:
                    await client.socket.close(code=1012)
                except (RuntimeError, OSError):
                    pass

    async def handle_message(self, name: str, client: Client, message: bytes) -> None:
        from app.storage.database import create_session
        from app.background.jobs.service import commit_and_notify

        if not message or len(message) > 8 * 1024 * 1024:
            raise ValueError("无效或过大的协同消息")
        async with chapter_lock(name.split(":", 1)[0]):
            if self.paused or name not in self.rooms:
                raise ConflictError("协同编辑已关闭")
            room = self.rooms[name]
            if message[0] == 1:
                previous_ids = set(room.awareness.states)
                room.awareness.apply_awareness_update(read_message(message[1:]), client)
                client.awareness_ids.update(set(room.awareness.states) - previous_ids)
                await self.broadcast(room, message)
                return
            if message[0] == 3:
                await client.send(
                    create_awareness_message(
                        room.awareness.encode_awareness_update(
                            list(room.awareness.states)
                        )
                    )
                )
                return
            if message[0] == 4:
                if json.loads(read_message(message[1:])) != {"type": "flush"}:
                    raise ValueError("无效的协同消息")
                await self.acknowledge(room, client)
                return
            if message[0] != 0 or len(message) < 2 or message[1] not in (0, 1, 2):
                raise ValueError("无效的同步消息")
            if message[1] == 0:
                reply = handle_sync_message(message[1:], room.document)
                if reply is not None:
                    await client.send(reply)
                return
            candidate = clone_document(room.document)
            handle_sync_message(message[1:], candidate)
            text_of(candidate)
            if candidate.get_update() == room.document.get_update():
                await self.acknowledge(room, client)
                return
            data = self.snapshot(name, candidate, room.version + 1)
            session = await create_session()
            try:
                if not await is_enabled(session):
                    raise ConflictError("协同编辑已关闭")
                await load_document(session, name)
                await persist_document(session, data)
                await commit_and_notify(session)
                # Publication follows the successful binary + text snapshot transaction.
                await self.publish(data)
            except BaseException:
                await session.rollback()
                raise
            finally:
                await session.close()


hub = CollaborationHub()


async def edit_chapter(session: AsyncSession, chapter_id: str, **edit: Any) -> dict:
    record = await document_record(session, chapter_id)
    # The caller holds the per-chapter lock until the binary state and revision
    # are committed. No external process or second database connection is used.
    saved = await load_document(session, room_for(record))
    result = hub.prepare(room_for(record), saved, **edit)
    await persist_document(session, result, record_activity=False)
    session.info.setdefault("collaboration_updates", []).append(result)
    return result


async def publish_committed_updates(session: AsyncSession) -> None:
    for data in session.info.pop("collaboration_updates", []):
        try:
            await hub.publish(data)
        except Exception:
            # SQL already owns the durable update. A fresh worker loads that state.
            logger.exception("Could not publish committed collaboration update")
            await hub.evict(data["room"])


@asynccontextmanager
async def rollback_guard(session: AsyncSession, revision_id: str):
    async with AsyncExitStack() as stack:
        if await is_enabled(session):
            from app.storage.repos import revision_repo

            revision = await revision_repo.get_by_id(session, revision_id)
            if revision is not None:
                chapters = await chapter_repo.list_metadata_by_project(
                    session, revision.project_id
                )
                for chapter in sorted(chapters, key=lambda item: item.id):
                    await stack.enter_async_context(chapter_lock(chapter.id))
        yield


async def prepare_rollback(
    session: AsyncSession, snapshots: dict, revisions: list
) -> dict:
    if not snapshots or not await is_enabled(session):
        return {}
    from app.storage.repos import commit_repo

    expected = {}
    for revision in revisions:
        for commit in await commit_repo.list_by_revision(session, revision.id):
            expected[commit.chapter_id] = commit.new_content
    results = {}
    for chapter_id, snapshot in snapshots.items():
        current = await chapter_repo.get_by_id(session, chapter_id)
        if current is None or not snapshot.exists:
            raise ConflictError(
                "协同模式下无法自动回滚章节创建或删除，请关闭实验功能后重试"
            )
        desired = snapshot.content or ""
        baseline = expected.get(chapter_id)
        if baseline is None:
            if current.content != desired:
                raise ConflictError("缺少安全回滚所需的 Agent 修改记录")
            continue
        # Merge nearby character changes into meaningful text ranges. Tiny
        # one-character inverse patches are often ambiguous in fiction prose.
        ranges = []
        for tag, i, j, a, b in SequenceMatcher(None, baseline, desired).get_opcodes():
            if tag == "equal":
                continue
            if ranges and i - ranges[-1][1] < 48:
                previous = ranges[-1]
                ranges[-1] = (previous[0], j, previous[2], b)
            else:
                ranges.append((i, j, a, b))
        edits = []
        for i, j, a, b in ranges:
            old = baseline[i:j]
            edits.append(
                {
                    "old": old,
                    "text": desired[a:b],
                    "left": baseline[max(0, i - 48) : i],
                    "right": baseline[j : j + 48],
                    "unique": bool(old) and baseline.count(old) == 1,
                }
            )
        record = await document_record(session, chapter_id)
        saved = await load_document(session, room_for(record))
        result = hub.prepare(room_for(record), saved, edits=list(reversed(edits)))
        results[chapter_id] = result
    # All chapter patches have been validated before changing the transaction.
    for result in results.values():
        await persist_document(session, result, record_activity=False)
        session.info.setdefault("collaboration_updates", []).append(result)
    return results
