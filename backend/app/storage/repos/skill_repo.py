# -*- coding: utf-8 -*-
"""Skill Repository - Skill 数据访问层。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.skill import Skill


async def create(session: AsyncSession, skill: Skill) -> Skill:
    session.add(skill)
    await session.flush()
    await session.refresh(skill)
    return skill


async def get_by_id(session: AsyncSession, skill_db_id: str) -> Skill | None:
    result = await session.execute(select(Skill).where(col(Skill.id) == skill_db_id))
    return result.scalar_one_or_none()


async def get_by_skill_id(session: AsyncSession, skill_id: str) -> Skill | None:
    if not skill_id:
        return None
    result = await session.execute(select(Skill).where(col(Skill.skill_id) == skill_id))
    return result.scalar_one_or_none()


async def get_all(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[Skill], int]:
    count_result = await session.execute(select(func.count(col(Skill.id))))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await session.execute(
        select(Skill)
        .order_by(col(Skill.created_at).asc(), col(Skill.id).asc())
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def list_by_skill_ids(session: AsyncSession, skill_ids: list[str]) -> list[Skill]:
    if not skill_ids:
        return []
    result = await session.execute(
        select(Skill).where(col(Skill.skill_id).in_(skill_ids))
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, skill: Skill) -> Skill:
    session.add(skill)
    await session.flush()
    await session.refresh(skill)
    return skill


async def delete(session: AsyncSession, skill: Skill) -> None:
    await session.delete(skill)
    await session.flush()
