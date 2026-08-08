# -*- coding: utf-8 -*-
"""AgentRule Repository - 规则数据访问层。"""

from sqlalchemy import func, or_, select
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


def _scope_filter(scope: str, project_id: str | None):
    if scope == "project":
        return col(AgentRule.project_id) == project_id
    return col(AgentRule.scope) == "global"


async def get_all(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 100,
    scope: str = "global",
    project_id: str | None = None,
) -> tuple[list[AgentRule], int]:
    scope_cond = _scope_filter(scope, project_id)
    count_result = await session.execute(select(func.count(col(AgentRule.id))).where(scope_cond))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await session.execute(
        select(AgentRule)
        .where(scope_cond)
        .order_by(col(AgentRule.order_index).asc(), col(AgentRule.created_at).asc())
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_all_ordered(
    session: AsyncSession,
    project_id: str | None = None,
) -> list[AgentRule]:
    cond = col(AgentRule.scope) == "global"
    if project_id:
        cond = or_(cond, col(AgentRule.project_id) == project_id)
    result = await session.execute(
        select(AgentRule)
        .where(cond, col(AgentRule.content) != "")
        .order_by(
            (col(AgentRule.scope) == "global").desc(),
            col(AgentRule.order_index).asc(),
            col(AgentRule.created_at).asc(),
        )
    )
    return list(result.scalars().all())


async def get_all_for_scope_counts(session: AsyncSession) -> list[AgentRule]:
    """返回所有规则用于统计各作用域数量，与列表展示保持一致，不按项目或内容过滤。"""
    result = await session.execute(select(AgentRule))
    return list(result.scalars().all())


async def get_max_order_index(
    session: AsyncSession,
    scope: str = "global",
    project_id: str | None = None,
) -> int:
    scope_cond = _scope_filter(scope, project_id)
    result = await session.execute(
        select(func.max(col(AgentRule.order_index))).where(scope_cond)
    )
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