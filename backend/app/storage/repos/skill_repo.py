# -*- coding: utf-8 -*-
"""Skill Repository - Skill 数据访问层。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.skills import BUILTIN_SKILL_ID_PREFIX
from app.storage.models.skill import Skill


def _custom_skill_filter():
    return col(Skill.id).not_like(f"{BUILTIN_SKILL_ID_PREFIX}%")


async def create(session: AsyncSession, skill: Skill) -> Skill:
    session.add(skill)
    await session.flush()
    await session.refresh(skill)
    return skill


async def get_by_id(session: AsyncSession, skill_db_id: str) -> Skill | None:
    result = await session.execute(select(Skill).where(col(Skill.id) == skill_db_id))
    return result.scalar_one_or_none()


async def upsert(session: AsyncSession, skill: Skill) -> Skill:
    existing = await get_by_id(session, skill.id)
    if existing is None:
        return await create(session, skill)

    existing.is_enabled = skill.is_enabled
    existing.updated_at = skill.updated_at
    return await update(session, existing)


async def get_all(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[Skill], int]:
    count_result = await session.execute(
        select(func.count(col(Skill.id))).where(_custom_skill_filter())
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await session.execute(
        select(Skill)
        .where(_custom_skill_filter())
        .order_by(col(Skill.created_at).asc(), col(Skill.id).asc())
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def list_page(
    session: AsyncSession,
    *,
    offset: int,
    limit: int,
) -> list[Skill]:
    result = await session.execute(
        select(Skill)
        .where(_custom_skill_filter())
        .order_by(col(Skill.created_at).asc(), col(Skill.id).asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_by_names(session: AsyncSession, names: list[str]) -> list[Skill]:
    if not names:
        return []
    result = await session.execute(
        select(Skill).where(_custom_skill_filter(), col(Skill.name).in_(names))
    )
    return list(result.scalars().all())


async def list_by_ids(session: AsyncSession, ids: list[str]) -> list[Skill]:
    if not ids:
        return []
    result = await session.execute(select(Skill).where(col(Skill.id).in_(ids)))
    return list(result.scalars().all())


async def get_all_names(session: AsyncSession) -> list[str]:
    result = await session.execute(select(col(Skill.name)).where(_custom_skill_filter()))
    return [row[0] for row in result.all()]


async def get_total(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(col(Skill.id))).where(_custom_skill_filter())
    )
    return result.scalar_one()


async def update(session: AsyncSession, skill: Skill) -> Skill:
    session.add(skill)
    await session.flush()
    await session.refresh(skill)
    return skill


async def delete(session: AsyncSession, skill: Skill) -> None:
    await session.delete(skill)
    await session.flush()
