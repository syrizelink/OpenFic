# -*- coding: utf-8 -*-
"""
Chapter Service - lapisan logika bisnis bab.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.editor_content_limits import validate_editor_content
from app.core.errors import NotFoundError
from app.memory.chapter.sequence import global_order_index
from app.storage.models.chapter import Chapter
from app.storage.models.volume import Volume
from app.storage.repos import (
    chapter_repo,
    chapter_summary_repo,
    project_repo,
    volume_repo,
)
from app.storage.services import writing_activity_service


@dataclass
class VolumeChapterGroup:
    """Volume beserta daftar babnya."""

    volume: Volume
    chapters: list[Chapter]


@dataclass
class VolumeTreeResult:
    """Hasil pohon volume-bab."""

    volumes: list[VolumeChapterGroup]
    total_chapters: int


@dataclass(frozen=True)
class MentionCandidate:
    """Kandidat mention percakapan."""

    kind: Literal["volume", "chapter"]
    id: str
    title: str
    label: str
    description: str | None = None


def _count_words(text: str) -> int:
    """
    Menghitung jumlah kata teks campuran Tionghoa-Inggris.

    Teks Tionghoa dihitung per karakter, teks Inggris dihitung per kata.

    Args:
        text: Teks yang akan dihitung.

    Returns:
        Jumlah kata.
    """
    if not text:
        return 0

    # Mencocokkan karakter Tionghoa
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    chinese_count = len(chinese_chars)

    # Setelah karakter Tionghoa dibuang, pisah dengan spasi untuk menghitung kata Inggris
    text_without_chinese = re.sub(r"[\u4e00-\u9fff]", " ", text)
    english_words = [w for w in text_without_chinese.split() if w.strip()]
    english_count = len(english_words)

    return chinese_count + english_count


def _display_volume_title(volume: Volume) -> str:
    title = volume.title.strip()
    return title or "Volume Tanpa Nama"


def _display_chapter_title(chapter: Chapter) -> str:
    title = chapter.title.strip()
    return title or "Bab Tanpa Nama"


def _match_rank(text: str, normalized_query: str) -> int:
    normalized_text = text.strip().lower()
    if not normalized_text:
        return 99
    if normalized_text == normalized_query:
        return 0
    if normalized_text.startswith(normalized_query):
        return 1
    if normalized_query in normalized_text:
        return 2
    return 99


async def _update_project_stats(session: AsyncSession, project_id: str) -> None:
    """
    Memperbarui informasi statistik proyek (jumlah kata dan jumlah bab).

    Args:
        session: session basis data.
        project_id: ID proyek.
    """
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        return

    # Memperbarui jumlah bab
    chapter_count = await chapter_repo.count_by_project(session, project_id)
    project.chapter_count = chapter_count

    # Memperbarui total jumlah kata
    total_word_count = await chapter_repo.get_total_word_count(session, project_id)
    project.word_count = total_word_count

    project.updated_at = datetime.now(UTC)
    await project_repo.update(session, project)


async def _update_volume_stats(session: AsyncSession, volume_id: str) -> None:
    """Memperbarui cache jumlah bab pada volume."""
    volume = await volume_repo.get_by_id(session, volume_id)
    if volume is None:
        return
    volume.chapter_count = await chapter_repo.count_by_volume(session, volume_id)
    volume.updated_at = datetime.now(UTC)
    await volume_repo.update_volume(session, volume)


async def create_chapter(
    session: AsyncSession,
    project_id: str,
    volume_id: str,
    title: str,
    content: str = "",
    word_count: int | None = None,
) -> Chapter:
    """
    Membuat bab.

    Args:
        session: session basis data.
        project_id: ID proyek.
        volume_id: ID volume.
        title: Judul bab.
        content: Isi bab, default kosong.
        word_count: Jumlah kata (dihitung frontend), dihitung backend bila None.

    Returns:
        Instance bab yang dibuat.

    Raises:
        NotFoundError: Proyek tidak ditemukan.
    """
    validate_editor_content(content)

    # Memeriksa apakah proyek ada
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"Proyek tidak ditemukan: {project_id}")
    volume = await volume_repo.get_by_id(session, volume_id)
    if volume is None or volume.project_id != project_id:
        raise NotFoundError(f"Volume tidak ditemukan: {volume_id}")

    # Mengambil nomor urut terbesar
    max_order = await chapter_repo.get_max_order(session, volume_id)

    # Memakai jumlah kata dari frontend, atau menghitung di backend
    final_word_count = word_count if word_count is not None else _count_words(content)

    # Membuat bab
    chapter = Chapter(
        project_id=project_id,
        volume_id=volume_id,
        title=title,
        content=content,
        word_count=final_word_count,
        order=max_order + 1,
    )
    chapter = await chapter_repo.create(session, chapter)

    await writing_activity_service.record_activity(
        session,
        project_id=project_id,
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        source="user",
        operation="create",
        old_word_count=0,
        new_word_count=chapter.word_count,
    )

    # Memperbarui statistik proyek
    await _update_volume_stats(session, volume_id)
    await _update_project_stats(session, project_id)

    from app.memory.chapter.summary_service import (
        maybe_enqueue_chapter_summary_for_new_chapter,
    )

    await maybe_enqueue_chapter_summary_for_new_chapter(session, chapter)

    from app.retrieval.chapter_index import safe_maybe_enqueue_auto_index
    from app.retrieval.index_status import schedule_emit_index_status

    await safe_maybe_enqueue_auto_index(session, project_id=project_id)
    schedule_emit_index_status(session, project_id)

    return chapter


async def get_chapter(session: AsyncSession, chapter_id: str) -> Chapter:
    """
    Mengambil bab.

    Args:
        session: session basis data.
        chapter_id: ID bab.

    Returns:
        Instance bab.

    Raises:
        NotFoundError: Bab tidak ditemukan.
    """
    chapter = await chapter_repo.get_by_id(session, chapter_id)
    if chapter is None:
        raise NotFoundError(f"Bab tidak ditemukan: {chapter_id}")
    return chapter


async def list_chapters(
    session: AsyncSession,
    project_id: str,
) -> VolumeTreeResult:
    """
    Mengambil pohon volume-bab proyek (bab tanpa isi teks).

    Args:
        session: session basis data.
        project_id: ID proyek.

    Returns:
        Hasil daftar bab.

    Raises:
        NotFoundError: Proyek tidak ditemukan.
    """
    # Memeriksa apakah proyek ada
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"Proyek tidak ditemukan: {project_id}")

    volumes = await volume_repo.list_by_project(session, project_id)
    chapters = await chapter_repo.list_metadata_by_project(session, project_id)
    chapters_by_volume: dict[str, list[Chapter]] = {volume.id: [] for volume in volumes}
    for chapter in chapters:
        chapters_by_volume.setdefault(chapter.volume_id, []).append(chapter)
    groups = [
        VolumeChapterGroup(
            volume=volume,
            chapters=chapters_by_volume.get(volume.id, []),
        )
        for volume in volumes
    ]
    return VolumeTreeResult(volumes=groups, total_chapters=len(chapters))


async def search_mention_candidates(
    session: AsyncSession,
    project_id: str,
    query: str,
    *,
    limit: int = 20,
) -> list[MentionCandidate]:
    """Mencari kandidat mention volume/bab yang dapat disisipkan ke percakapan."""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"Proyek tidak ditemukan: {project_id}")

    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    clamped_limit = max(1, min(limit, 50))
    matched_volumes = await volume_repo.search_by_project(
        session,
        project_id,
        normalized_query,
        limit=clamped_limit,
    )
    matched_chapters = await chapter_repo.search_with_volume_by_project(
        session,
        project_id,
        normalized_query,
        limit=clamped_limit,
    )

    scored_candidates: list[tuple[int, int, MentionCandidate]] = []

    for index, volume in enumerate(matched_volumes):
        title = _display_volume_title(volume)
        scored_candidates.append(
            (
                _match_rank(title, normalized_query),
                index,
                MentionCandidate(
                    kind="volume",
                    id=volume.id,
                    title=title,
                    label=title,
                ),
            )
        )

    base_index = len(scored_candidates)
    for offset, (chapter, volume) in enumerate(matched_chapters):
        chapter_title = _display_chapter_title(chapter)
        volume_title = _display_volume_title(volume)
        chapter_rank = _match_rank(chapter_title, normalized_query)
        volume_rank = _match_rank(volume_title, normalized_query)
        scored_candidates.append(
            (
                min(chapter_rank, volume_rank + 3),
                base_index + offset,
                MentionCandidate(
                    kind="chapter",
                    id=chapter.id,
                    title=chapter_title,
                    label=chapter_title,
                    description=volume_title,
                ),
            )
        )

    scored_candidates.sort(
        key=lambda item: (
            item[0],
            0 if item[2].kind == "volume" else 1,
            item[1],
        )
    )
    return [candidate for _, _, candidate in scored_candidates[:clamped_limit]]


@dataclass
class ChapterSearchMatch:
    """Baris yang cocok pada pencarian isi bab."""

    line_number: int
    line_text: str


@dataclass
class ChapterSearchResult:
    """Hasil pencarian isi bab."""

    chapter_id: str
    chapter_title: str
    volume_title: str
    matches: list[ChapterSearchMatch]


@dataclass
class ChapterSearchResponse:
    """Respons pencarian isi bab."""

    results: list[ChapterSearchResult]
    total_chapters: int
    total_matches: int


async def search_chapters(
    session: AsyncSession,
    project_id: str,
    query: str,
) -> ChapterSearchResponse:
    """Mencari bab berdasarkan isi."""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"Proyek tidak ditemukan: {project_id}")

    if not query.strip():
        return ChapterSearchResponse(results=[], total_chapters=0, total_matches=0)

    entries = await chapter_repo.search_by_content(session, project_id, query)

    results: list[ChapterSearchResult] = []
    total_matches = 0
    lower_query = query.lower()

    for chapter, volume in entries:
        lines = chapter.content.split("\n")
        matches: list[ChapterSearchMatch] = []
        for line_number, line in enumerate(lines, start=1):
            if lower_query in line.lower():
                matches.append(
                    ChapterSearchMatch(
                        line_number=line_number,
                        line_text=line,
                    )
                )

        if matches:
            results.append(
                ChapterSearchResult(
                    chapter_id=chapter.id,
                    chapter_title=_display_chapter_title(chapter),
                    volume_title=_display_volume_title(volume),
                    matches=matches,
                )
            )
            total_matches += len(matches)

    return ChapterSearchResponse(
        results=results,
        total_chapters=len(results),
        total_matches=total_matches,
    )


async def update_chapter(
    session: AsyncSession,
    chapter_id: str,
    title: str | None = None,
    content: str | None = None,
    word_count: int | None = None,
) -> Chapter:
    """
    Memperbarui bab.

    Args:
        session: session basis data.
        chapter_id: ID bab.
        title: Judul baru, opsional.
        content: Isi baru, opsional.
        word_count: Jumlah kata (dihitung frontend), dihitung backend bila None.

    Returns:
        Instance bab setelah diperbarui.

    Raises:
        NotFoundError: Bab tidak ditemukan.
    """
    chapter = await get_chapter(session, chapter_id)
    old_word_count = chapter.word_count
    old_content = chapter.content

    title_changed = False
    if title is not None and title != chapter.title:
        chapter.title = title
        title_changed = True

    content_changed = False
    if content is not None and content != chapter.content:
        validate_editor_content(content)
        chapter.content = content
        # Utamakan jumlah kata dari frontend, jika tidak ada hitung di backend
        chapter.word_count = (
            word_count if word_count is not None else _count_words(content)
        )
        content_changed = True
    elif word_count is not None and word_count != chapter.word_count:
        # Bila hanya word_count yang dikirim tanpa content, perbarui hanya saat jumlah kata benar berubah
        chapter.word_count = word_count
        content_changed = True

    if title_changed or content_changed:
        chapter.updated_at = datetime.now(UTC)
    chapter = await chapter_repo.update_chapter(session, chapter)

    # Bila ada perubahan apa pun, perbarui statistik proyek (termasuk updated_at)
    if title_changed or content_changed:
        if content_changed:
            await writing_activity_service.record_activity(
                session,
                project_id=chapter.project_id,
                chapter_id=chapter.id,
                chapter_title=chapter.title,
                source="user",
                operation="update",
                old_word_count=old_word_count,
                new_word_count=chapter.word_count,
            )
        await _update_project_stats(session, chapter.project_id)
    if content is not None and content != old_content:
        from app.retrieval.chapter_index import (
            ChapterIndexIntegrationService,
            safe_maybe_enqueue_auto_index,
        )
        from app.retrieval.index_status import schedule_emit_index_status

        await ChapterIndexIntegrationService().mark_chapter_stale_if_changed(
            session,
            chapter,
        )
        await safe_maybe_enqueue_auto_index(session, project_id=chapter.project_id)
        schedule_emit_index_status(session, chapter.project_id)
    return chapter


async def delete_chapter(
    session: AsyncSession,
    chapter_id: str,
    *,
    record_activity: bool = True,
    activity_source: writing_activity_service.WritingActivitySource = "user",
    revision_id: str | None = None,
    task_id: str | None = None,
    agent_session_id: str | None = None,
) -> None:
    """
    Menghapus bab.

    Args:
        session: session basis data.
        chapter_id: ID bab.

    Raises:
        NotFoundError: Bab tidak ditemukan.
    """
    chapter = await get_chapter(session, chapter_id)
    project_id = chapter.project_id
    volume_id = chapter.volume_id
    deleted_volume_order = chapter.order
    chapters = await chapter_repo.list_metadata_by_project(session, project_id)
    volumes = await volume_repo.list_by_project(session, project_id)
    deleted_global_order = global_order_index(chapters, volumes)[chapter_id]
    old_title = chapter.title
    old_word_count = chapter.word_count

    from app.retrieval.chapter_index import ChapterIndexIntegrationService
    from app.retrieval.index_status import schedule_emit_index_status

    await ChapterIndexIntegrationService().delete_chapter_index(session, chapter)
    schedule_emit_index_status(session, project_id)

    await chapter_summary_repo.delete_by_chapter_id(session, chapter_id)
    long_term_summaries = (
        await chapter_summary_repo.list_long_term_summaries_by_project(
            session, project_id
        )
    )
    affected_ranges = list(
        {
            (summary.start_order, summary.end_order)
            for summary in long_term_summaries
            if summary.start_order is not None
            and summary.end_order is not None
            and summary.end_order >= deleted_global_order
        }
    )
    if affected_ranges:
        await chapter_summary_repo.delete_long_term_summaries_by_ranges(
            session, project_id, affected_ranges
        )

    # Menghapus bab
    await chapter_repo.delete(session, chapter)

    if record_activity:
        await writing_activity_service.record_activity(
            session,
            project_id=project_id,
            chapter_id=chapter_id,
            chapter_title=old_title,
            source=activity_source,
            operation="delete",
            old_word_count=old_word_count,
            new_word_count=0,
            revision_id=revision_id,
            task_id=task_id,
            agent_session_id=agent_session_id,
        )

    # Menyesuaikan urutan bab berikutnya
    max_order = await chapter_repo.get_max_order(session, volume_id)
    if deleted_volume_order <= max_order:
        # Kurangi 1 pada order semua bab yang order > deleted_volume_order
        await chapter_repo.shift_orders(
            session, volume_id, deleted_volume_order + 1, max_order, -1
        )

    # Memperbarui statistik proyek
    await _update_volume_stats(session, volume_id)
    await _update_project_stats(session, project_id)


async def delete_chapters_in_volume(session: AsyncSession, volume_id: str) -> None:
    """Menghapus bab dalam volume secara massal.

    Menghindari pemindaian proyek berulang dan hitung ulang statistik per bab.
    """
    chapters = await chapter_repo.list_by_volume(session, volume_id)
    if not chapters:
        return

    project_id = chapters[0].project_id
    project_chapters = await chapter_repo.list_metadata_by_project(session, project_id)
    volumes = await volume_repo.list_by_project(session, project_id)
    global_orders = global_order_index(project_chapters, volumes)
    deleted_global_orders = [
        global_orders[chapter.id]
        for chapter in chapters
        if chapter.id in global_orders
    ]

    from app.retrieval.chapter_index import ChapterIndexIntegrationService
    from app.retrieval.index_status import schedule_emit_index_status

    index_service = ChapterIndexIntegrationService()
    for chapter in chapters:
        await index_service.delete_chapter_index(session, chapter)
    schedule_emit_index_status(session, project_id)

    await chapter_summary_repo.delete_by_chapter_ids(
        session, [chapter.id for chapter in chapters]
    )
    if deleted_global_orders:
        long_term_summaries = (
            await chapter_summary_repo.list_long_term_summaries_by_project(
                session, project_id
            )
        )
        first_deleted_order = min(deleted_global_orders)
        affected_ranges = [
            (summary.start_order, summary.end_order)
            for summary in long_term_summaries
            if summary.start_order is not None
            and summary.end_order is not None
            and summary.end_order >= first_deleted_order
        ]
        await chapter_summary_repo.delete_long_term_summaries_by_ranges(
            session, project_id, affected_ranges
        )

    await chapter_repo.delete_by_volume(session, volume_id)
    for chapter in chapters:
        await writing_activity_service.record_activity(
            session,
            project_id=project_id,
            chapter_id=chapter.id,
            chapter_title=chapter.title,
            source="user",
            operation="delete",
            old_word_count=chapter.word_count,
            new_word_count=0,
        )
    await _update_project_stats(session, project_id)


async def reorder_chapters(
    session: AsyncSession,
    volume_id: str,
    chapter_ids: list[str],
) -> list[Chapter]:
    """
    Menata ulang urutan bab secara massal.

    Args:
        session: session basis data.
        volume_id: ID volume.
        chapter_ids: Daftar ID bab dalam urutan baru.

    Returns:
        Daftar bab setelah diperbarui.

    Raises:
        NotFoundError: Bab tidak ditemukan atau bukan milik volume yang ditentukan.
        ValueError: Jumlah bab tidak cocok.
    """
    chapters = await chapter_repo.get_metadata_by_ids(session, chapter_ids)
    chapter_map = {c.id: c for c in chapters}

    if len(chapters) != len(chapter_ids):
        missing = [cid for cid in chapter_ids if cid not in chapter_map]
        raise NotFoundError(f"Bab tidak ditemukan: {missing}")

    for chapter in chapters:
        if chapter.volume_id != volume_id:
            raise ValueError(f"Bab {chapter.id} bukan milik volume {volume_id}")

    orders = {
        chapter_id: new_order
        for new_order, chapter_id in enumerate(chapter_ids, start=1)
        if chapter_map[chapter_id].order != new_order
    }

    updated_at = await chapter_repo.update_orders(session, orders)
    if updated_at is not None:
        for chapter_id, chapter_order in orders.items():
            chapter = chapter_map[chapter_id]
            set_committed_value(chapter, "order", chapter_order)
            set_committed_value(chapter, "updated_at", updated_at)

    updated_chapters = chapters
    order_lookup = {cid: idx for idx, cid in enumerate(chapter_ids)}
    updated_chapters.sort(key=lambda c: order_lookup.get(c.id, 0))
    return updated_chapters


async def move_chapter_to_volume(
    session: AsyncSession,
    chapter_id: str,
    volume_id: str,
    *,
    record_activity: bool = True,
    activity_source: writing_activity_service.WritingActivitySource = "user",
    revision_id: str | None = None,
    task_id: str | None = None,
    agent_session_id: str | None = None,
) -> Chapter:
    """Memindahkan bab antarvolume, menambahkannya di akhir volume tujuan."""
    chapter = await get_chapter(session, chapter_id)
    source_volume_id = chapter.volume_id
    if source_volume_id == volume_id:
        return chapter

    target_volume = await volume_repo.get_by_id(session, volume_id)
    if target_volume is None or target_volume.project_id != chapter.project_id:
        raise NotFoundError(f"Volume tidak ditemukan: {volume_id}")

    old_order = chapter.order
    chapter.order = 0
    await chapter_repo.update_chapter(session, chapter)

    source_max_order = await chapter_repo.get_max_order(session, source_volume_id)
    if old_order <= source_max_order:
        await chapter_repo.shift_orders(
            session, source_volume_id, old_order + 1, source_max_order, -1
        )

    target_max_order = await chapter_repo.get_max_order(session, volume_id)
    chapter.volume_id = volume_id
    chapter.order = target_max_order + 1
    chapter.updated_at = datetime.now(UTC)
    chapter = await chapter_repo.update_chapter(session, chapter)

    await _update_volume_stats(session, source_volume_id)
    await _update_volume_stats(session, volume_id)
    await _update_project_stats(session, chapter.project_id)
    from app.retrieval.chapter_index import (
        ChapterIndexIntegrationService,
        safe_maybe_enqueue_auto_index,
    )
    from app.retrieval.index_status import schedule_emit_index_status

    await ChapterIndexIntegrationService().mark_chapter_stale_if_indexed(
        session,
        chapter,
    )
    await safe_maybe_enqueue_auto_index(session, project_id=chapter.project_id)
    schedule_emit_index_status(session, chapter.project_id)
    if record_activity:
        await writing_activity_service.record_activity(
            session,
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            chapter_title=chapter.title,
            source=activity_source,
            operation="move_to_volume",
            old_word_count=chapter.word_count,
            new_word_count=chapter.word_count,
            revision_id=revision_id,
            task_id=task_id,
            agent_session_id=agent_session_id,
        )
    return chapter
