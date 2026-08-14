from __future__ import annotations

import asyncio
import weakref

from loguru import logger


class AgentRunRegistry:
    """Tracks active agent stream tasks so they can be cancelled explicitly."""

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, asyncio.Task[None]]] = {}
        self._cancelled_sessions: set[str] = set()
        # Lifecycle locks are only needed while a caller holds a reference to
        # them. A weak table prevents every historical session id from being
        # retained for the lifetime of the worker.
        self._session_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )
        self._lock = asyncio.Lock()

    def session_lock(self, session_id: str) -> asyncio.Lock:
        """Serialize lifecycle transitions for one parent agent session."""

        return self._session_locks.setdefault(session_id, asyncio.Lock())

    async def register(
        self,
        session_id: str,
        task: asyncio.Task[None],
        *,
        clear_cancelled: bool = True,
    ) -> None:
        async with self._lock:
            if clear_cancelled:
                self._cancelled_sessions.discard(session_id)
            session_tasks = self._tasks.setdefault(session_id, {})
            existing = session_tasks.get("__parent__")
            if existing is not None and not existing.done() and existing is not task:
                logger.bind(session_id=session_id).warning("replacing active agent run task")
                existing.cancel()
            session_tasks["__parent__"] = task

    async def try_register_parent(
        self,
        session_id: str,
        task: asyncio.Task[None],
    ) -> bool:
        async with self._lock:
            session_tasks = self._tasks.setdefault(session_id, {})
            existing = session_tasks.get("__parent__")
            if existing is not None and not existing.done() and existing is not task:
                return False
            self._cancelled_sessions.discard(session_id)
            session_tasks["__parent__"] = task
            return True

    async def register_child(
        self,
        session_id: str,
        child_run_id: str,
        task: asyncio.Task[None],
        *,
        clear_cancelled: bool = True,
    ) -> None:
        async with self._lock:
            if clear_cancelled:
                self._cancelled_sessions.discard(session_id)
            session_tasks = self._tasks.setdefault(session_id, {})
            existing = session_tasks.get(child_run_id)
            if existing is not None and not existing.done() and existing is not task:
                logger.bind(
                    session_id=session_id,
                    child_run_id=child_run_id,
                ).warning("replacing active child agent run task")
                existing.cancel()
            session_tasks[child_run_id] = task

    async def try_register_child(
        self,
        session_id: str,
        child_run_id: str,
        task: asyncio.Task[None],
        *,
        clear_cancelled: bool = True,
    ) -> bool:
        async with self._lock:
            session_tasks = self._tasks.setdefault(session_id, {})
            existing = session_tasks.get(child_run_id)
            if existing is not None and not existing.done() and existing is not task:
                return False
            if clear_cancelled:
                self._cancelled_sessions.discard(session_id)
            session_tasks[child_run_id] = task
            return True

    async def unregister(self, session_id: str, task: asyncio.Task[None]) -> bool:
        async with self._lock:
            session_tasks = self._tasks.get(session_id)
            if not session_tasks:
                return False
            for run_id, registered in list(session_tasks.items()):
                if registered is task:
                    session_tasks.pop(run_id, None)
                    if not session_tasks:
                        self._tasks.pop(session_id, None)
                    return True
            return False

    async def unregister_child(
        self,
        session_id: str,
        child_run_id: str,
        task: asyncio.Task[None] | None = None,
    ) -> bool:
        async with self._lock:
            session_tasks = self._tasks.get(session_id)
            if not session_tasks or child_run_id not in session_tasks:
                return False
            if task is not None and session_tasks[child_run_id] is not task:
                return False
            session_tasks.pop(child_run_id, None)
            if not session_tasks:
                self._tasks.pop(session_id, None)
            return True

    async def is_child_running(self, session_id: str, child_run_id: str) -> bool:
        async with self._lock:
            task = (self._tasks.get(session_id) or {}).get(child_run_id)
            return task is not None and not task.done()

    async def cancel_child(self, session_id: str, child_run_id: str) -> bool:
        async with self._lock:
            task = (self._tasks.get(session_id) or {}).get(child_run_id)
            if task is None or task.done():
                return False
            task.cancel()
            return True

    async def cancel(self, session_id: str) -> bool:
        async with self._lock:
            self._cancelled_sessions.add(session_id)
            session_tasks = self._tasks.get(session_id) or {}
            tasks = [task for task in session_tasks.values() if not task.done()]
            if not tasks:
                return False
            for task in tasks:
                task.cancel()
            return True

    async def mark_cancelled(self, session_id: str) -> asyncio.Task[None] | None:
        async with self._lock:
            self._cancelled_sessions.add(session_id)
            task = (self._tasks.get(session_id) or {}).get("__parent__")
            if task is not None and not task.done():
                return task
            return None

    async def cancel_task(self, session_id: str, task: asyncio.Task[None]) -> bool:
        """Cancel only a task that is still the registered task for a session.

        The identity check is important for cancellation requests that race a
        newly registered run: a stale cancellation must not affect that run.
        """

        async with self._lock:
            session_tasks = self._tasks.get(session_id) or {}
            if task not in session_tasks.values() or task.done():
                return False
            task.cancel()
            return True

    async def is_cancelled(self, session_id: str) -> bool:
        async with self._lock:
            return session_id in self._cancelled_sessions

    async def is_running(self, session_id: str) -> bool:
        async with self._lock:
            session_tasks = self._tasks.get(session_id) or {}
            return any(not task.done() for task in session_tasks.values())

    async def has_running_tasks(self) -> bool:
        async with self._lock:
            return any(
                not task.done()
                for session_tasks in self._tasks.values()
                for task in session_tasks.values()
            )

    async def is_parent_running(self, session_id: str) -> bool:
        async with self._lock:
            task = (self._tasks.get(session_id) or {}).get("__parent__")
            return task is not None and not task.done()

    async def clear_cancelled(self, session_id: str) -> None:
        async with self._lock:
            self._cancelled_sessions.discard(session_id)

    async def cancel_all(self) -> int:
        async with self._lock:
            tasks = [
                task
                for session_tasks in self._tasks.values()
                for task in session_tasks.values()
                if not task.done()
            ]
            self._tasks.clear()

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return len(tasks)


_RUN_REGISTRY = AgentRunRegistry()


def get_agent_run_registry() -> AgentRunRegistry:
    return _RUN_REGISTRY
