from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from typing import Hashable

_LOCKS: dict[Hashable, asyncio.Lock] = {}
_GUARD = asyncio.Lock()


async def keyed_lock(key: Hashable) -> asyncio.Lock:
    async with _GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _LOCKS[key] = lock
        return lock


@asynccontextmanager
async def keyed_locks(keys: Iterable[Hashable]) -> AsyncIterator[None]:
    locks = [await keyed_lock(key) for key in sorted(set(keys), key=repr)]
    acquired: list[asyncio.Lock] = []
    try:
        for lock in locks:
            await lock.acquire()
            acquired.append(lock)
        yield
    finally:
        for lock in reversed(acquired):
            lock.release()
