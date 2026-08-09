from __future__ import annotations

import asyncio
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