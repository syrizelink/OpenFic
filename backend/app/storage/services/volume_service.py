# -*- coding: utf-8 -*-
"""
Volume Service - lapisan logika bisnis volume.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.storage.models.volume import Volume
from app.storage.repos import chapter_repo, project_repo, volume_repo

DEFAULT_VOLUME_TITLE = "Volume 1"
UNSET = object()


async def create_default_volume(session: AsyncSession, project_id: str) -> Volume:
    """Membuat volume default untuk proyek."""
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
    """Menambahkan volume di akhir proyek."""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"Proyek tidak ditemukan: {project_id}")

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
    """Mengambil detail volume."""
    volume = await volume_repo.get_by_id(session, volume_id)
    if volume is None:
        raise NotFoundError(f"Volume tidak ditemukan: {volume_id}")
    return volume


async def list_volumes(session: AsyncSession, project_id: str) -> list[Volume]:
    """Menampilkan seluruh volume dalam proyek."""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"Proyek tidak ditemukan: {project_id}")
    return await volume_repo.list_by_project(session, project_id)


async def update_volume(
    session: AsyncSession,
    volume_id: str,
    title: str | None = None,
    description: str | None | object = UNSET,
) -> Volume:
    """Memperbarui volume."""
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
    """Menyegarkan cache jumlah bab volume."""
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
    """Menghapus volume, volume tidak kosong memerlukan cascade=true."""
    volume = await get_volume(session, volume_id)
    project_id = volume.project_id
    deleted_order = volume.order
    volume_count = await volume_repo.count_by_project(session, project_id)
    if volume_count <= 1:
        raise ValidationError("Proyek harus menyisakan minimal satu volume")

    chapter_count = await chapter_repo.count_by_volume(session, volume_id)
    if chapter_count > 0 and not cascade:
        raise ValidationError("Volume tidak kosong, penghapusan memerlukan cascade=true")

    if cascade:
        from app.storage.services import chapter_service

        await chapter_service.delete_chapters_in_volume(session, volume_id)

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
    """Menyesuaikan urutan volume."""
    volume = await get_volume(session, volume_id)
    old_order = volume.order
    project_id = volume.project_id
    volume_count = await volume_repo.count_by_project(session, project_id)
    if new_order < 1 or new_order > volume_count:
        raise ValueError(f"Posisi urutan tidak valid: {new_order}, rentang valid 1-{volume_count}")
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
