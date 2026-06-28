# -*- coding: utf-8 -*-
"""
Note Repository - 笔记数据访问层。
"""

from sqlalchemy import case as sa_case
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.note import Note


async def create(session: AsyncSession, note: Note) -> Note:
    session.add(note)
    await session.flush()
    await session.refresh(note)
    return note


async def get_by_id(session: AsyncSession, note_id: str) -> Note | None:
    result = await session.execute(select(Note).where(col(Note.id) == note_id))
    return result.scalar_one_or_none()


async def list_by_project(
    session: AsyncSession,
    project_id: str,
    *,
    include_hidden: bool = True,
) -> list[Note]:
    stmt = (
        select(Note)
        .where(col(Note.project_id) == project_id)
        .order_by(col(Note.title).asc())
    )
    if not include_hidden:
        stmt = stmt.where(col(Note.is_hidden) == False)  # noqa: E712
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_mention_candidates(
    session: AsyncSession,
    project_id: str,
    query: str,
    *,
    limit: int,
    include_hidden: bool = False,
) -> list[Note]:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    title_expr = func.lower(func.coalesce(col(Note.title), ""))
    match_rank = sa_case(
        (title_expr == normalized_query, 0),
        (title_expr.like(f"{normalized_query}%"), 1),
        (title_expr.contains(normalized_query), 2),
        else_=99,
    )

    stmt = (
        select(Note)
        .where(
            col(Note.project_id) == project_id,
            title_expr.contains(normalized_query),
        )
        .order_by(match_rank.asc(), col(Note.title).asc())
        .limit(limit)
    )
    if not include_hidden:
        stmt = stmt.where(col(Note.is_hidden) == False)  # noqa: E712
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_by_content(
    session: AsyncSession,
    project_id: str,
    query: str,
) -> list[Note]:
    """按笔记内容搜索笔记。"""
    normalized_query = query.strip()
    if not normalized_query:
        return []

    result = await session.execute(
        select(Note)
        .where(
            col(Note.project_id) == project_id,
            col(Note.content).ilike(f"%{normalized_query}%"),
        )
        .order_by(col(Note.title).asc())
    )
    return list(result.scalars().all())


async def update_note(session: AsyncSession, note: Note) -> Note:
    session.add(note)
    await session.flush()
    await session.refresh(note)
    return note


async def delete(session: AsyncSession, note: Note) -> None:
    await session.delete(note)
    await session.flush()
