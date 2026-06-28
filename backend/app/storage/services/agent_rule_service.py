# -*- coding: utf-8 -*-
"""AgentRule Service - 规则业务逻辑层。"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.models.agent_rule import AgentRule
from app.storage.repos import agent_rule_repo


@dataclass
class AgentRuleListResult:
    items: list[AgentRule]
    total: int
    page: int
    page_size: int


async def create_rule(
    session: AsyncSession,
    *,
    title: str = "",
    content: str = "",
) -> AgentRule:
    max_order = await agent_rule_repo.get_max_order_index(session)
    rule = AgentRule(
        title=title,
        content=content,
        order_index=max_order + 1,
    )
    return await agent_rule_repo.create(session, rule)


async def get_rule(session: AsyncSession, rule_id: str) -> AgentRule:
    rule = await agent_rule_repo.get_by_id(session, rule_id)
    if rule is None:
        raise NotFoundError(f"规则不存在: {rule_id}")
    return rule


async def list_rules(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> AgentRuleListResult:
    items, total = await agent_rule_repo.get_all(session, page, page_size)
    return AgentRuleListResult(items=items, total=total, page=page, page_size=page_size)


async def list_all_rules(session: AsyncSession) -> list[AgentRule]:
    return await agent_rule_repo.get_all_ordered(session)


async def update_rule(
    session: AsyncSession,
    rule_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
) -> AgentRule:
    rule = await get_rule(session, rule_id)
    if title is not None:
        rule.title = title
    if content is not None:
        rule.content = content
    rule.updated_at = datetime.now(UTC)
    return await agent_rule_repo.update(session, rule)


async def reorder_rules(session: AsyncSession, rule_ids: list[str]) -> list[AgentRule]:
    rules = await agent_rule_repo.get_by_ids(session, rule_ids)
    rule_map = {r.id: r for r in rules}

    now = datetime.now(UTC)
    updated: list[AgentRule] = []
    for idx, rule_id in enumerate(rule_ids):
        rule = rule_map.get(rule_id)
        if rule is None:
            continue
        rule.order_index = idx
        rule.updated_at = now
        await agent_rule_repo.update(session, rule)
        updated.append(rule)
    return updated


async def delete_rule(session: AsyncSession, rule_id: str) -> None:
    rule = await get_rule(session, rule_id)
    await agent_rule_repo.delete(session, rule)
