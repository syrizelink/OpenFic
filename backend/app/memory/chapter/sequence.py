# -*- coding: utf-8 -*-
"""
Fungsi helper urutan baca global.

Menyediakan fungsi murni yang, setelah mengurutkan berdasarkan (volume.order, chapter.order),
membuat urutan baca berurutan tingkat proyek melalui enumerasi (dimulai dari 1).
"""

from app.storage.models.chapter import Chapter
from app.storage.models.volume import Volume


def global_reading_sequence(
    chapters: list[Chapter], volumes: list[Volume]
) -> list[tuple[int, Chapter]]:
    """
    Mengembalikan [(global_order, chapter), ...] terurut menurut urutan baca global, mulai dari 1.

    Kunci pengurutan: (volume.order, chapter.order).
    Jika volume_id tidak ada di dalam volumes, bab tersebut ditempatkan di akhir urutan.
    """
    volume_map = {v.id: v for v in volumes}

    sorted_chapters = sorted(
        chapters,
        key=lambda ch: (
            volume_map[ch.volume_id].order if ch.volume_id in volume_map else float("inf"),
            ch.order,
        ),
    )
    return [(i, ch) for i, ch in enumerate(sorted_chapters, 1)]


def global_order_index(chapters: list[Chapter], volumes: list[Volume]) -> dict[str, int]:
    """Mengembalikan {chapter_id: global_order}."""
    return {ch.id: ord_num for ord_num, ch in global_reading_sequence(chapters, volumes)}


def chapter_by_global_order(
    chapters: list[Chapter], volumes: list[Volume]
) -> dict[int, Chapter]:
    """Mengembalikan {global_order: chapter}."""
    return {ord_num: ch for ord_num, ch in global_reading_sequence(chapters, volumes)}
