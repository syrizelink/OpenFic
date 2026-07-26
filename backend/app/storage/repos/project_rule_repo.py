# -*- coding: utf-8 -*-
"""ProjectRule Repository - 项目规则数据访问层。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.project_rule import ProjectRule


async def create(session: AsyncSession, rule: ProjectRule) -> ProjectRule:
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return rule


async def get_by_id(session: AsyncSession, rule_id: str) -> ProjectRule | None:
    result = await session.execute(select(ProjectRule).where(col(ProjectRule.id) == rule_id))
    return result.scalar_one_or_none()


async def get_all_by_project(
    session: AsyncSession,
    project_id: str,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[ProjectRule], int]:
    count_result = await session.execute(
        select(func.count(col(ProjectRule.id))).where(col(ProjectRule.project_id) == project_id)
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await session.execute(
        select(ProjectRule)
        .where(col(ProjectRule.project_id) == project_id)
        .order_by(col(ProjectRule.order_index).asc(), col(ProjectRule.created_at).asc())
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_all_ordered(session: AsyncSession, project_id: str) -> list[ProjectRule]:
    result = await session.execute(
        select(ProjectRule)
        .where(col(ProjectRule.project_id) == project_id)
        .where(col(ProjectRule.content) != "")
        .order_by(col(ProjectRule.order_index).asc(), col(ProjectRule.created_at).asc())
    )
    return list(result.scalars().all())


async def get_max_order_index(session: AsyncSession, project_id: str) -> int:
    result = await session.execute(
        select(func.max(col(ProjectRule.order_index))).where(
            col(ProjectRule.project_id) == project_id
        )
    )
    return result.scalar_one() or 0


async def get_by_ids(session: AsyncSession, rule_ids: list[str]) -> list[ProjectRule]:
    if not rule_ids:
        return []
    result = await session.execute(
        select(ProjectRule).where(col(ProjectRule.id).in_(rule_ids))
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, rule: ProjectRule) -> ProjectRule:
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    return rule


async def delete(session: AsyncSession, rule: ProjectRule) -> None:
    await session.delete(rule)
    await session.flush()
