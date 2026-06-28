# -*- coding: utf-8 -*-
"""
Chapter Repository - 章节数据访问层。
"""

from datetime import UTC, datetime

from sqlalchemy import case, delete as sql_delete
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.chapter import Chapter
from app.storage.models.volume import Volume


async def create(session: AsyncSession, chapter: Chapter) -> Chapter:
    """
    创建章节。

    Args:
        session: 数据库 session。
        chapter: 章节实例。

    Returns:
        创建后的章节实例。
    """
    session.add(chapter)
    await session.flush()
    await session.refresh(chapter)
    return chapter


async def get_by_id(session: AsyncSession, chapter_id: str) -> Chapter | None:
    """
    根据 ID 获取章节。

    Args:
        session: 数据库 session。
        chapter_id: 章节 ID。

    Returns:
        章节实例，如果不存在则返回 None。
    """
    result = await session.execute(select(Chapter).where(col(Chapter.id) == chapter_id))
    return result.scalar_one_or_none()


async def get_by_ids(session: AsyncSession, chapter_ids: list[str]) -> list[Chapter]:
    """根据 ID 列表批量获取章节。"""
    if not chapter_ids:
        return []
    result = await session.execute(
        select(Chapter).where(col(Chapter.id).in_(chapter_ids))
    )
    return list(result.scalars().all())


async def list_by_project(
    session: AsyncSession,
    project_id: str,
) -> list[Chapter]:
    """
    获取项目下的所有章节列表。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。

    Returns:
        章节列表，按 order 排序。
    """
    result = await session.execute(
        select(Chapter)
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(col(Chapter.project_id) == project_id)
        .order_by(col(Volume.order).asc(), col(Chapter.order).asc())
    )
    return list(result.scalars().all())


async def search_with_volume_by_project(
    session: AsyncSession,
    project_id: str,
    query: str,
    *,
    limit: int,
) -> list[tuple[Chapter, Volume]]:
    """按章节标题或所属卷标题搜索章节。"""
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    chapter_title_expr = func.lower(func.coalesce(col(Chapter.title), ""))
    volume_title_expr = func.lower(func.coalesce(col(Volume.title), ""))
    match_rank = case(
        (chapter_title_expr == normalized_query, 0),
        (chapter_title_expr.like(f"{normalized_query}%"), 1),
        (chapter_title_expr.contains(normalized_query), 2),
        (volume_title_expr == normalized_query, 3),
        (volume_title_expr.like(f"{normalized_query}%"), 4),
        else_=5,
    )

    result = await session.execute(
        select(Chapter, Volume)
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(
            col(Chapter.project_id) == project_id,
            or_(
                chapter_title_expr.contains(normalized_query),
                volume_title_expr.contains(normalized_query),
            ),
        )
        .order_by(
            match_rank.asc(),
            col(Volume.order).asc(),
            col(Chapter.order).asc(),
        )
        .limit(limit)
    )
    return [(chapter, volume) for chapter, volume in result.all()]


async def search_by_content(
    session: AsyncSession,
    project_id: str,
    query: str,
) -> list[tuple[Chapter, Volume]]:
    """按章节内容搜索章节，返回匹配的章节及所属卷。"""
    normalized_query = query.strip()
    if not normalized_query:
        return []

    result = await session.execute(
        select(Chapter, Volume)
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(
            col(Chapter.project_id) == project_id,
            col(Chapter.content).ilike(f"%{normalized_query}%"),
        )
        .order_by(col(Volume.order).asc(), col(Chapter.order).asc())
    )
    return [(chapter, volume) for chapter, volume in result.all()]


async def list_by_volume(
    session: AsyncSession,
    volume_id: str,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> list[Chapter]:
    """分页获取卷下章节列表。"""
    stmt = (
        select(Chapter)
        .where(col(Chapter.volume_id) == volume_id)
        .order_by(col(Chapter.order).asc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_by_project_page(
    session: AsyncSession,
    project_id: str,
    *,
    offset: int,
    limit: int,
) -> list[Chapter]:
    """分页获取项目下章节列表。"""
    result = await session.execute(
        select(Chapter)
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(col(Chapter.project_id) == project_id)
        .order_by(col(Volume.order).asc(), col(Chapter.order).asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_by_project(session: AsyncSession, project_id: str) -> int:
    """
    获取项目下的章节总数。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。

    Returns:
        章节总数。
    """
    result = await session.execute(
        select(func.count(col(Chapter.id))).where(col(Chapter.project_id) == project_id)
    )
    return result.scalar_one()


async def count_by_volume(session: AsyncSession, volume_id: str) -> int:
    """获取卷下的章节总数。"""
    result = await session.execute(
        select(func.count(col(Chapter.id))).where(col(Chapter.volume_id) == volume_id)
    )
    return result.scalar_one()


async def get_max_order(session: AsyncSession, volume_id: str) -> int:
    """
    获取卷下的最大排序序号。

    Args:
        session: 数据库 session。
        volume_id: 卷 ID。

    Returns:
        最大排序序号，如果没有章节则返回 0。
    """
    result = await session.execute(
        select(func.max(col(Chapter.order))).where(col(Chapter.volume_id) == volume_id)
    )
    max_order = result.scalar_one_or_none()
    return max_order if max_order is not None else 0


async def get_total_word_count(session: AsyncSession, project_id: str) -> int:
    """
    获取项目下所有章节的总字数。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。

    Returns:
        总字数。
    """
    result = await session.execute(
        select(func.sum(col(Chapter.word_count))).where(
            col(Chapter.project_id) == project_id
        )
    )
    total = result.scalar_one_or_none()
    return total if total is not None else 0


async def update_chapter(session: AsyncSession, chapter: Chapter) -> Chapter:
    """
    更新章节。

    Args:
        session: 数据库 session。
        chapter: 章节实例。

    Returns:
        更新后的章节实例。
    """
    session.add(chapter)
    await session.flush()
    await session.refresh(chapter)
    return chapter


async def delete(session: AsyncSession, chapter: Chapter) -> None:
    """
    删除章节。

    Args:
        session: 数据库 session。
        chapter: 章节实例。
    """
    await session.delete(chapter)
    await session.flush()


async def update_orders(
    session: AsyncSession,
    orders: dict[str, int],
) -> None:
    """
    批量更新章节排序（两阶段，避免 UNIQUE 冲突）。

    Args:
        session: 数据库 session。
        orders: {chapter_id: new_order} 映射。
    """
    if not orders:
        return

    now = datetime.now(UTC)
    ids = list(orders.keys())

    # Phase 1: set to negative temp values to avoid UNIQUE(volume_id, order) conflicts
    temp_whens = {cid: -(i + 1) for i, cid in enumerate(ids)}
    await session.execute(
        update(Chapter)
        .where(col(Chapter.id).in_(ids))
        .values(
            order=case(
                *[(col(Chapter.id) == cid, val) for cid, val in temp_whens.items()],
            ),
            updated_at=now,
        )
    )
    await session.flush()

    # Phase 2: set final values
    await session.execute(
        update(Chapter)
        .where(col(Chapter.id).in_(ids))
        .values(
            order=case(
                *[(col(Chapter.id) == cid, order) for cid, order in orders.items()],
            ),
            updated_at=now,
        )
    )
    await session.flush()


async def shift_orders(
    session: AsyncSession,
    volume_id: str,
    start_order: int,
    end_order: int,
    delta: int,
) -> None:
    """
    批量调整排序序号。

    用于章节移动时调整其他章节的顺序。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。
        start_order: 起始序号（包含）。
        end_order: 结束序号（包含）。
        delta: 调整量（+1 或 -1）。
    """
    await session.execute(
        update(Chapter)
        .where(
            col(Chapter.volume_id) == volume_id,
            col(Chapter.order) >= start_order,
            col(Chapter.order) <= end_order,
        )
        .values(order=col(Chapter.order) + delta)
    )
    await session.flush()


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    """
    删除项目下的所有章节。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。
    """
    await session.execute(
        sql_delete(Chapter).where(col(Chapter.project_id) == project_id)
    )
    await session.flush()


async def get_by_project_and_order(
    session: AsyncSession,
    project_id: str,
    order: int,
) -> Chapter | None:
    """根据项目内扁平序号查询章节。"""
    if order < 1:
        return None
    chapters = await list_by_project(session, project_id)
    if order > len(chapters):
        return None
    return chapters[order - 1]


async def get_by_volume_and_order(
    session: AsyncSession,
    volume_id: str,
    order: int,
) -> Chapter | None:
    """根据 volume_id 与卷内章节序号查询章节。"""
    stmt = select(Chapter).where(
        col(Chapter.volume_id) == volume_id,
        col(Chapter.order) == order,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
