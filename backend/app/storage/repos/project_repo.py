# -*- coding: utf-8 -*-
"""
Project Repository - 项目数据访问层。
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.core.pinyin import to_pinyin, to_pinyin_initials
from app.storage.database import is_sqlite_backend
from app.storage.models.project import Project

SORT_COLUMNS = {
    "updated_at": Project.updated_at,
    "created_at": Project.created_at,
    "title": Project.title,
}


def _escape_like_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _pinyin_search_pattern(search: str) -> str | None:
    compact_search = "".join(search.split())
    if not compact_search.isascii() or not compact_search.isalpha():
        return None
    return f"%{_escape_like_pattern(compact_search.lower())}%"


def _matches_project_search(project: Project, search: str) -> bool:
    normalized_search = search.strip().casefold()
    text_values = (project.title, project.description or "")
    if any(normalized_search in value.casefold() for value in text_values):
        return True

    pinyin_search = "".join(search.split()).casefold()
    return any(
        pinyin_search in converted
        for value in text_values
        for converted in (
            to_pinyin(value).casefold(),
            to_pinyin_initials(value).casefold(),
        )
    )


def _sort_projects_in_memory(
    projects: list[Project], sort_by: str, sort_order: str
) -> list[Project]:
    def value_for_sort(project: Project) -> str:
        if sort_by == "title":
            return to_pinyin(project.title).casefold()
        return str(getattr(project, sort_by, project.updated_at))

    projects.sort(key=lambda project: project.id)
    projects.sort(key=value_for_sort, reverse=sort_order == "desc")
    return projects


def _apply_search(stmt, search: str | None):
    normalized_search = (search or "").strip()
    if not normalized_search:
        return stmt

    pattern = f"%{_escape_like_pattern(normalized_search)}%"
    predicates = [
        col(Project.title).ilike(pattern, escape="\\"),
        col(Project.description).ilike(pattern, escape="\\"),
    ]
    pinyin_pattern = _pinyin_search_pattern(normalized_search)
    if pinyin_pattern and is_sqlite_backend():
        predicates.extend(
            (
                func.pinyin_full(col(Project.title)).like(pinyin_pattern, escape="\\"),
                func.pinyin_initials(col(Project.title)).like(pinyin_pattern, escape="\\"),
                func.pinyin_full(col(Project.description)).like(pinyin_pattern, escape="\\"),
                func.pinyin_initials(col(Project.description)).like(pinyin_pattern, escape="\\"),
            )
        )
    return stmt.where(or_(*predicates))


async def create(session: AsyncSession, project: Project) -> Project:
    """
    创建项目。

    Args:
        session: 数据库 session。
        project: 项目实例。

    Returns:
        创建后的项目实例。
    """
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project


async def get_by_id(session: AsyncSession, project_id: str) -> Project | None:
    """
    根据 ID 获取项目。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。

    Returns:
        项目实例，如果不存在则返回 None。
    """
    result = await session.execute(select(Project).where(col(Project.id) == project_id))
    return result.scalar_one_or_none()


async def list_all(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
    *,
    search: str | None = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
) -> list[Project]:
    """
    获取项目列表。

    Args:
        session: 数据库 session。
        offset: 偏移量。
        limit: 每页数量。

    Returns:
        项目列表。
    """
    needs_in_memory_sort = not is_sqlite_backend() and sort_by == "title"
    needs_in_memory_search = (
        search is not None
        and not is_sqlite_backend()
        and _pinyin_search_pattern(search)
    )
    if needs_in_memory_sort or needs_in_memory_search:
        result = await session.execute(select(Project))
        projects = [
            project
            for project in result.scalars().all()
            if not search or _matches_project_search(project, search)
        ]
        _sort_projects_in_memory(projects, sort_by, sort_order)
        return projects[offset : offset + limit]

    sort_column = SORT_COLUMNS.get(sort_by, Project.updated_at)
    sortable_expression = (
        func.pinyin_full(col(Project.title))
        if sort_by == "title" and is_sqlite_backend()
        else col(sort_column)
    )
    order_expression = sortable_expression.asc() if sort_order == "asc" else sortable_expression.desc()
    stmt = (
        _apply_search(select(Project), search)
        .order_by(order_expression, col(Project.id).asc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count(session: AsyncSession, *, search: str | None = None) -> int:
    """
    获取项目总数。

    Args:
        session: 数据库 session。

    Returns:
        项目总数。
    """
    if search and not is_sqlite_backend() and _pinyin_search_pattern(search):
        result = await session.execute(select(Project))
        return sum(
            _matches_project_search(project, search)
            for project in result.scalars().all()
        )

    result = await session.execute(
        _apply_search(select(func.count(col(Project.id))), search)
    )
    return result.scalar_one()


async def update(session: AsyncSession, project: Project) -> Project:
    """
    更新项目。

    Args:
        session: 数据库 session。
        project: 项目实例。

    Returns:
        更新后的项目实例。
    """
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project


async def delete(session: AsyncSession, project: Project) -> None:
    """
    删除项目。

    Args:
        session: 数据库 session。
        project: 项目实例。
    """
    await session.delete(project)
    await session.flush()
