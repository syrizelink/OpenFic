# -*- coding: utf-8 -*-
"""
Note Category Repository - 笔记分类数据访问层。
"""

from sqlalchemy import case as sa_case
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.note import NoteCategory


async def create(session: AsyncSession, category: NoteCategory) -> NoteCategory:
    session.add(category)
    await session.flush()
    await session.refresh(category)
    return category


async def get_by_id(session: AsyncSession, category_id: str) -> NoteCategory | None:
    result = await session.execute(
        select(NoteCategory).where(col(NoteCategory.id) == category_id)
    )
    return result.scalar_one_or_none()


async def list_by_project(
    session: AsyncSession,
    project_id: str,
) -> list[NoteCategory]:
    result = await session.execute(
        select(NoteCategory)
        .where(col(NoteCategory.project_id) == project_id)
        .order_by(col(NoteCategory.title).asc())
    )
    return list(result.scalars().all())


async def get_by_parent(
    session: AsyncSession,
    parent_id: str | None,
) -> list[NoteCategory]:
    if parent_id is None:
        stmt = select(NoteCategory).where(col(NoteCategory.parent_id).is_(None))
    else:
        stmt = select(NoteCategory).where(col(NoteCategory.parent_id) == parent_id)
    stmt = stmt.order_by(col(NoteCategory.title).asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_category(
    session: AsyncSession, category: NoteCategory
) -> NoteCategory:
    session.add(category)
    await session.flush()
    await session.refresh(category)
    return category


async def delete(session: AsyncSession, category: NoteCategory) -> None:
    await session.delete(category)
    await session.flush()


async def search_mention_candidates(
    session: AsyncSession,
    project_id: str,
    query: str,
    *,
    limit: int,
) -> list[NoteCategory]:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    title_expr = func.lower(func.coalesce(col(NoteCategory.title), ""))
    match_rank = sa_case(
        (title_expr == normalized_query, 0),
        (title_expr.like(f"{normalized_query}%"), 1),
        (title_expr.contains(normalized_query), 2),
        else_=99,
    )

    stmt = (
        select(NoteCategory)
        .where(
            col(NoteCategory.project_id) == project_id,
            title_expr.contains(normalized_query),
        )
        .order_by(match_rank.asc(), col(NoteCategory.title).asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
