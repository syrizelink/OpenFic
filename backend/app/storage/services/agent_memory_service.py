# -*- coding: utf-8 -*-
"""AgentMemory Service - 记忆业务逻辑层。"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.models.agent_memory import AgentMemory
from app.storage.repos import agent_memory_repo


@dataclass
class AgentMemoryListResult:
    items: list[AgentMemory]
    total: int
    page: int
    page_size: int


async def create_memory(
    session: AsyncSession,
    *,
    content: str = "",
) -> AgentMemory:
    max_order = await agent_memory_repo.get_max_order_index(session)
    memory = AgentMemory(
        content=content,
        order_index=max_order + 1,
    )
    return await agent_memory_repo.create(session, memory)


async def get_memory(session: AsyncSession, memory_id: str) -> AgentMemory:
    memory = await agent_memory_repo.get_by_id(session, memory_id)
    if memory is None:
        raise NotFoundError(f"记忆不存在: {memory_id}")
    return memory


async def list_memories(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> AgentMemoryListResult:
    items, total = await agent_memory_repo.get_all(session, page, page_size)
    return AgentMemoryListResult(items=items, total=total, page=page, page_size=page_size)


async def list_all_memories(session: AsyncSession) -> list[AgentMemory]:
    return await agent_memory_repo.get_all_ordered(session)


async def update_memory(
    session: AsyncSession,
    memory_id: str,
    *,
    content: str | None = None,
) -> AgentMemory:
    memory = await get_memory(session, memory_id)
    if content is not None:
        memory.content = content
    memory.updated_at = datetime.now(UTC)
    return await agent_memory_repo.update(session, memory)


async def reorder_memories(session: AsyncSession, memory_ids: list[str]) -> list[AgentMemory]:
    memories = await agent_memory_repo.get_by_ids(session, memory_ids)
    memory_map = {m.id: m for m in memories}

    now = datetime.now(UTC)
    updated: list[AgentMemory] = []
    for idx, memory_id in enumerate(memory_ids):
        memory = memory_map.get(memory_id)
        if memory is None:
            continue
        memory.order_index = idx
        memory.updated_at = now
        await agent_memory_repo.update(session, memory)
        updated.append(memory)
    return updated


async def delete_memory(session: AsyncSession, memory_id: str) -> None:
    memory = await get_memory(session, memory_id)
    await agent_memory_repo.delete(session, memory)
