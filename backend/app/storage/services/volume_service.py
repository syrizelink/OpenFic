# -*- coding: utf-8 -*-
"""
Volume Service - 卷业务逻辑层。
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.storage.models.volume import Volume
from app.storage.repos import chapter_repo, project_repo, volume_repo

DEFAULT_VOLUME_TITLE = "第一卷"
UNSET = object()


async def create_default_volume(session: AsyncSession, project_id: str) -> Volume:
    """为项目创建默认卷。"""
    volume = Volume(
        project_id=project_id,
        title=DEFAULT_VOLUME_TITLE,
        description=None,
        order=1,
        chapter_count=0,
    )
    return await volume_repo.create(session, volume)


async def create_volume(
    session: AsyncSession,
    project_id: str,
    title: str,
    description: str | None = None,
) -> Volume:
    """在项目末尾追加卷。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    max_order = await volume_repo.get_max_order(session, project_id)
    volume = Volume(
        project_id=project_id,
        title=title,
        description=description,
        order=max_order + 1,
        chapter_count=0,
    )
    return await volume_repo.create(session, volume)


async def get_volume(session: AsyncSession, volume_id: str) -> Volume:
    """获取卷详情。"""
    volume = await volume_repo.get_by_id(session, volume_id)
    if volume is None:
        raise NotFoundError(f"卷不存在: {volume_id}")
    return volume


async def list_volumes(session: AsyncSession, project_id: str) -> list[Volume]:
    """列出项目下全部卷。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")
    return await volume_repo.list_by_project(session, project_id)


async def update_volume(
    session: AsyncSession,
    volume_id: str,
    title: str | None = None,
    description: str | None | object = UNSET,
) -> Volume:
    """更新卷。"""
    volume = await get_volume(session, volume_id)
    changed = False
    if title is not None and title != volume.title:
        volume.title = title
        changed = True
    if description is not UNSET and description != volume.description:
        volume.description = description if isinstance(description, str) else None
        changed = True
    if changed:
        volume.updated_at = datetime.now(UTC)
        volume = await volume_repo.update_volume(session, volume)
    return volume


async def refresh_volume_chapter_count(
    session: AsyncSession,
    volume_id: str,
) -> Volume | None:
    """刷新卷章节数缓存。"""
    volume = await volume_repo.get_by_id(session, volume_id)
    if volume is None:
        return None
    volume.chapter_count = await chapter_repo.count_by_volume(session, volume_id)
    volume.updated_at = datetime.now(UTC)
    return await volume_repo.update_volume(session, volume)


async def delete_volume(
    session: AsyncSession,
    volume_id: str,
    *,
    cascade: bool = False,
) -> None:
    """删除卷，非空卷需要 cascade=true。"""
    volume = await get_volume(session, volume_id)
    project_id = volume.project_id
    deleted_order = volume.order
    volume_count = await volume_repo.count_by_project(session, project_id)
    if volume_count <= 1:
        raise ValidationError("项目至少需要保留一个卷")

    chapter_count = await chapter_repo.count_by_volume(session, volume_id)
    if chapter_count > 0 and not cascade:
        raise ValidationError("卷非空，删除时需要 cascade=true")

    if cascade:
        from app.storage.services import chapter_service

        chapters = await chapter_repo.list_by_volume(session, volume_id)
        for chapter in list(chapters):
            await chapter_service.delete_chapter(session, chapter.id)

    await volume_repo.delete(session, volume)

    max_order = await volume_repo.get_max_order(session, project_id)
    if deleted_order <= max_order:
        await volume_repo.shift_orders(
            session, project_id, deleted_order + 1, max_order, -1
        )


async def move_volume(
    session: AsyncSession,
    volume_id: str,
    new_order: int,
) -> Volume:
    """调整卷顺序。"""
    volume = await get_volume(session, volume_id)
    old_order = volume.order
    project_id = volume.project_id
    volume_count = await volume_repo.count_by_project(session, project_id)
    if new_order < 1 or new_order > volume_count:
        raise ValueError(f"无效的排序位置: {new_order}，有效范围为 1-{volume_count}")
    if old_order == new_order:
        return volume

    volume.order = 0
    await volume_repo.update_volume(session, volume)

    if old_order < new_order:
        await volume_repo.shift_orders(session, project_id, old_order + 1, new_order, -1)
    else:
        await volume_repo.shift_orders(session, project_id, new_order, old_order - 1, 1)

    volume.order = new_order
    volume.updated_at = datetime.now(UTC)
    return await volume_repo.update_volume(session, volume)
