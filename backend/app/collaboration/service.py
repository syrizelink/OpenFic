"""Hocuspocus worker lifecycle and transactional Yjs persistence.

A single worker owns live Y.Docs. SQL transactions store binary state and the
business text snapshot together; per-chapter locks serialize Agent commits and
browser persistence. There is deliberately no fallback to whole-text writes.
"""

import asyncio
import base64
from contextlib import AsyncExitStack, asynccontextmanager
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import secrets
import shutil
from typing import Any

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


class CollaborationWorker:
    def __init__(self) -> None:
        self.process: asyncio.subprocess.Process | None = None
        self.port = 0
        self.secret = secrets.token_urlsafe(32)
        self._start_lock = asyncio.Lock()
        self._pending: dict[int, asyncio.Future] = {}
        self._sequence = 0
        self._reader: asyncio.Task | None = None
        self._stderr: asyncio.Task | None = None
        self._callbacks: set[asyncio.Task] = set()
        self._ready: asyncio.Future | None = None
        self._lease = None

    async def start(self) -> None:
        async with self._start_lock:
            if (
                self.process is not None
                and self.process.returncode is None
                and self.port
            ):
                return
            node = os.getenv("OPENFIC_NODE_BINARY") or shutil.which("node")
            bundled = Path(__file__).with_name("server.bundle.cjs")
            source = (
                Path(__file__).resolve().parents[3] / "collaboration" / "server.mjs"
            )
            script = bundled if bundled.exists() else source
            if not node or not script.exists():
                raise ConflictError(
                    "协同编辑需要 Node.js 22+ 和 Hocuspocus 服务，请先安装协同服务依赖"
                )
            if self._lease is None:
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
                    raise ConflictError(
                        "协同服务已由另一后端进程运行；实验功能只支持单进程部署"
                    ) from exc
                self._lease = lease
            self.port = 0
            self._ready = asyncio.get_running_loop().create_future()
            self.process = await asyncio.create_subprocess_exec(
                node,
                str(script),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=16 * 1024 * 1024,
                env={
                    **os.environ,
                    "OPENFIC_COLLABORATION_SECRET": self.secret,
                    "ELECTRON_RUN_AS_NODE": "1",
                },
            )
            self._reader = asyncio.create_task(self._read())
            self._stderr = asyncio.create_task(self._read_stderr())
            try:
                await asyncio.wait_for(asyncio.shield(self._ready), 15)
            except Exception as exc:
                await self.stop()
                raise ConflictError(
                    "Hocuspocus 启动失败，请检查 Node.js 和协同服务依赖"
                ) from exc

    async def _send(self, message: dict) -> None:
        if (
            self.process is None
            or self.process.stdin is None
            or self.process.returncode is not None
        ):
            raise ConflictError("协同服务已断开，请重新连接")
        self.process.stdin.write(
            (json.dumps(message, ensure_ascii=False) + "\n").encode()
        )
        await self.process.stdin.drain()

    async def call(self, method: str, **data: Any) -> Any:
        await self.start()
        self._sequence += 1
        request_id = self._sequence
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self._send({"id": request_id, "method": method, **data})
            return await asyncio.wait_for(future, 30)
        finally:
            self._pending.pop(request_id, None)

    async def _read(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        try:
            while line := await self.process.stdout.readline():
                message = json.loads(line)
                if message.get("ready"):
                    self.port = message["port"]
                    if self._ready is not None and not self._ready.done():
                        self._ready.set_result(None)
                elif "requestId" in message:
                    task = asyncio.create_task(self._callback(message))
                    self._callbacks.add(task)
                    task.add_done_callback(self._callbacks.discard)
                elif future := self._pending.get(message.get("id")):
                    if not future.done():
                        if message.get("error"):
                            future.set_exception(ConflictError(message["error"]))
                        else:
                            future.set_result(message.get("result"))
        finally:
            self.port = 0
            for future in [*self._pending.values(), self._ready]:
                if future is not None and not future.done():
                    future.set_exception(ConflictError("Hocuspocus 连接已关闭"))

    async def _read_stderr(self) -> None:
        assert self.process is not None and self.process.stderr is not None
        while line := await self.process.stderr.readline():
            logger.debug("Hocuspocus: {}", line.decode().strip())

    async def _callback(self, message: dict) -> None:
        from app.storage.database import create_session
        from app.background.jobs.service import commit_and_notify

        session = await create_session()
        try:
            if message["method"] == "load":
                result = await load_document(session, message["room"])
            else:
                async with chapter_lock(message["room"].split(":", 1)[0]):
                    if not await is_enabled(session):
                        raise ConflictError("协同编辑已关闭")
                    latest = await self.call("snapshot", room=message["room"])
                    await persist_document(session, latest)
                    await commit_and_notify(session)
                result = True
            await self._send({"requestId": message["requestId"], "result": result})
        except Exception as exc:
            await session.rollback()
            logger.warning("Collaboration {} failed: {}", message["method"], exc)
            await self._send({"requestId": message["requestId"], "error": str(exc)})
        finally:
            await session.close()

    async def stop(self) -> None:
        if self.process is not None and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        tasks = [
            task
            for task in [self._reader, self._stderr, *self._callbacks]
            if task is not None
        ]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._callbacks.clear()
        self.process = None
        self.port = 0
        if self._lease is not None:
            self._lease.close()
            self._lease = None


worker = CollaborationWorker()


async def edit_chapter(session: AsyncSession, chapter_id: str, **edit: Any) -> dict:
    record = await document_record(session, chapter_id)
    # Seed Agent-only rooms directly, so loading never reads uncommitted SQL
    # state through a second connection. Existing editors keep their live Y.Doc.
    saved = await load_document(session, room_for(record))
    result = await worker.call("edit", room=room_for(record), seed=saved, **edit)
    await persist_document(session, result, record_activity=False)
    session.info.setdefault("collaboration_updates", []).append(result)
    return result


async def publish_committed_updates(session: AsyncSession) -> None:
    for data in session.info.pop("collaboration_updates", []):
        try:
            await worker.call("apply", room=data["room"], state=data["state"])
        except Exception:
            # SQL already owns the durable update. A fresh worker loads that state.
            logger.exception("Could not publish committed collaboration update")
            await worker.stop()


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
        result = await worker.call(
            "restore", room=room_for(record), seed=saved, edits=list(reversed(edits))
        )
        results[chapter_id] = result
    # All chapter patches have been validated before changing the transaction.
    for result in results.values():
        await persist_document(session, result, record_activity=False)
        session.info.setdefault("collaboration_updates", []).append(result)
    return results
