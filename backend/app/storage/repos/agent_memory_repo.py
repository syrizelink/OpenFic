# -*- coding: utf-8 -*-
"""AgentMemory Repository - 记忆数据访问层。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.agent_memory import AgentMemory


async def create(session: AsyncSession, memory: AgentMemory) -> AgentMemory:
    session.add(memory)
    await session.flush()
    await session.refresh(memory)
    return memory


async def get_by_id(session: AsyncSession, memory_id: str) -> AgentMemory | None:
    result = await session.execute(select(AgentMemory).where(col(AgentMemory.id) == memory_id))
    return result.scalar_one_or_none()


async def get_all(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[AgentMemory], int]:
    count_result = await session.execute(select(func.count(col(AgentMemory.id))))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await session.execute(
        select(AgentMemory)
        .order_by(col(AgentMemory.order_index).asc(), col(AgentMemory.created_at).asc())
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_all_ordered(session: AsyncSession) -> list[AgentMemory]:
    result = await session.execute(
        select(AgentMemory)
        .where(col(AgentMemory.content) != "")
        .order_by(col(AgentMemory.order_index).asc(), col(AgentMemory.created_at).asc())
    )
    return list(result.scalars().all())


async def get_max_order_index(session: AsyncSession) -> int:
    result = await session.execute(select(func.max(col(AgentMemory.order_index))))
    return result.scalar_one() or 0


async def get_by_ids(session: AsyncSession, memory_ids: list[str]) -> list[AgentMemory]:
    if not memory_ids:
        return []
    result = await session.execute(
        select(AgentMemory).where(col(AgentMemory.id).in_(memory_ids))
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, memory: AgentMemory) -> AgentMemory:
    session.add(memory)
    await session.flush()
    await session.refresh(memory)
    return memory


async def delete(session: AsyncSession, memory: AgentMemory) -> None:
    await session.delete(memory)
    await session.flush()
