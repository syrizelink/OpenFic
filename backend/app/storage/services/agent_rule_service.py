# -*- coding: utf-8 -*-
"""AgentRule Service - 规则业务逻辑层。"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.utils.tiktoken import count_tokens
from app.storage.models.agent_rule import AgentRule
from app.storage.repos import agent_rule_repo, project_repo


@dataclass
class AgentRuleListResult:
    items: list[AgentRule]
    total: int
    page: int
    page_size: int


@dataclass
class AgentRuleScope:
    scope: str
    project_id: str | None
    title: str
    rule_count: int


async def create_rule(
    session: AsyncSession,
    *,
    title: str = "",
    content: str = "",
    scope: str = "global",
    project_id: str | None = None,
) -> AgentRule:
    if scope == "project":
        if not project_id or await project_repo.get_by_id(session, project_id) is None:
            raise ValueError("project 作用域必须指定有效的项目")
    resolved_project_id = project_id if scope == "project" else None
    max_order = await agent_rule_repo.get_max_order_index(session, scope, resolved_project_id)
    rule = AgentRule(
        title=title,
        content=content,
        scope=scope,
        project_id=resolved_project_id,
        token_count=count_tokens(content),
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
    scope: str = "global",
    project_id: str | None = None,
) -> AgentRuleListResult:
    resolved_project_id = project_id if scope == "project" else None
    items, total = await agent_rule_repo.get_all(
        session, page, page_size, scope, resolved_project_id
    )
    return AgentRuleListResult(items=items, total=total, page=page, page_size=page_size)


async def list_all_rules(
    session: AsyncSession,
    project_id: str | None = None,
) -> list[AgentRule]:
    return await agent_rule_repo.get_all_ordered(session, project_id)


async def list_scopes(
    session: AsyncSession,
    rules: list[AgentRule] | None = None,
) -> list[AgentRuleScope]:
    """返回规则作用域：全局置顶，其余按项目修改时间倒序。"""
    if rules is None:
        rules = await agent_rule_repo.get_all_for_scope_counts(session)
    projects = await project_repo.list_all(session, offset=0, limit=1000)

    counts: dict[str, int] = {}
    for rule in rules:
        key = "global" if rule.scope != "project" else f"project:{rule.project_id}"
        counts[key] = counts.get(key, 0) + 1

    global_count = counts.get("global", 0)
    scopes: list[AgentRuleScope] = [
        AgentRuleScope(scope="global", project_id=None, title="全局", rule_count=global_count)
    ]
    for project in projects:
        key = f"project:{project.id}"
        scopes.append(
            AgentRuleScope(
                scope="project",
                project_id=project.id,
                title=project.title,
                rule_count=counts.get(key, 0),
            )
        )
    return scopes


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
        rule.token_count = count_tokens(content)
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