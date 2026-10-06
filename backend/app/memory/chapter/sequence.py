"""全局阅读序位 helper 函数。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.models.chapter import Chapter
    from app.storage.models.volume import Volume


def global_reading_sequence(
    chapters: list[Chapter], volumes: list[Volume]
) -> list[tuple[int, Chapter]]:
    """
    返回按全局阅读序排序的 [(global_order, chapter), ...]，从 1 开始。

    排序键：(volume.order, chapter.order)。
    volume_id 不存在于 volumes 中时，该章节排到序列末尾。
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
    """返回 {chapter_id: global_order}。"""
    return {ch.id: ord_num for ord_num, ch in global_reading_sequence(chapters, volumes)}


def chapter_by_global_order(
    chapters: list[Chapter], volumes: list[Volume]
) -> dict[int, Chapter]:
    """返回 {global_order: chapter}。"""
    return {ord_num: ch for ord_num, ch in global_reading_sequence(chapters, volumes)}
