# -*- coding: utf-8 -*-
"""ProjectRule Service - 项目规则业务逻辑层。"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.models.project_rule import ProjectRule
from app.storage.repos import project_repo, project_rule_repo


@dataclass
class ProjectRuleListResult:
    items: list[ProjectRule]
    total: int
    page: int
    page_size: int


async def _require_project(session: AsyncSession, project_id: str) -> None:
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")


async def create_rule(
    session: AsyncSession,
    project_id: str,
    *,
    title: str = "",
    content: str = "",
) -> ProjectRule:
    await _require_project(session, project_id)
    max_order = await project_rule_repo.get_max_order_index(session, project_id)
    rule = ProjectRule(
        project_id=project_id,
        title=title,
        content=content,
        order_index=max_order + 1,
    )
    return await project_rule_repo.create(session, rule)


async def get_rule(session: AsyncSession, project_id: str, rule_id: str) -> ProjectRule:
    rule = await project_rule_repo.get_by_id(session, rule_id)
    if rule is None or rule.project_id != project_id:
        raise NotFoundError(f"规则不存在: {rule_id}")
    return rule


async def list_rules(
    session: AsyncSession,
    project_id: str,
    page: int = 1,
    page_size: int = 100,
) -> ProjectRuleListResult:
    await _require_project(session, project_id)
    items, total = await project_rule_repo.get_all_by_project(session, project_id, page, page_size)
    return ProjectRuleListResult(items=items, total=total, page=page, page_size=page_size)


async def list_all_rules(session: AsyncSession, project_id: str) -> list[ProjectRule]:
    return await project_rule_repo.get_all_ordered(session, project_id)


async def update_rule(
    session: AsyncSession,
    project_id: str,
    rule_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
) -> ProjectRule:
    rule = await get_rule(session, project_id, rule_id)
    if title is not None:
        rule.title = title
    if content is not None:
        rule.content = content
    rule.updated_at = datetime.now(UTC)
    return await project_rule_repo.update(session, rule)


async def reorder_rules(
    session: AsyncSession, project_id: str, rule_ids: list[str]
) -> list[ProjectRule]:
    await _require_project(session, project_id)
    rules = await project_rule_repo.get_by_ids(session, rule_ids)
    rule_map = {r.id: r for r in rules if r.project_id == project_id}

    now = datetime.now(UTC)
    updated: list[ProjectRule] = []
    for idx, rule_id in enumerate(rule_ids):
        rule = rule_map.get(rule_id)
        if rule is None:
            continue
        rule.order_index = idx
        rule.updated_at = now
        await project_rule_repo.update(session, rule)
        updated.append(rule)
    return updated


async def delete_rule(session: AsyncSession, project_id: str, rule_id: str) -> None:
    rule = await get_rule(session, project_id, rule_id)
    await project_rule_repo.delete(session, rule)
