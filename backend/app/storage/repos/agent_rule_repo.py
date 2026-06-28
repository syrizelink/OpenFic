# -*- coding: utf-8 -*-
"""AgentRule Repository - 规则数据访问层。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.agent_rule import AgentRule


async def create(session: AsyncSession, rule: AgentRule) -> AgentRule:
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return rule


async def get_by_id(session: AsyncSession, rule_id: str) -> AgentRule | None:
    result = await session.execute(select(AgentRule).where(col(AgentRule.id) == rule_id))
    return result.scalar_one_or_none()


async def get_all(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[AgentRule], int]:
    count_result = await session.execute(select(func.count(col(AgentRule.id))))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await session.execute(
        select(AgentRule)
        .order_by(col(AgentRule.order_index).asc(), col(AgentRule.created_at).asc())
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_all_ordered(session: AsyncSession) -> list[AgentRule]:
    result = await session.execute(
        select(AgentRule)
        .where(col(AgentRule.content) != "")
        .order_by(col(AgentRule.order_index).asc(), col(AgentRule.created_at).asc())
    )
    return list(result.scalars().all())


async def get_max_order_index(session: AsyncSession) -> int:
    result = await session.execute(select(func.max(col(AgentRule.order_index))))
    return result.scalar_one() or 0


async def get_by_ids(session: AsyncSession, rule_ids: list[str]) -> list[AgentRule]:
    if not rule_ids:
        return []
    result = await session.execute(
        select(AgentRule).where(col(AgentRule.id).in_(rule_ids))
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, rule: AgentRule) -> AgentRule:
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return rule


async def delete(session: AsyncSession, rule: AgentRule) -> None:
    await session.delete(rule)
    await session.flush()
