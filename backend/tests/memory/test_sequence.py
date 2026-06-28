# -*- coding: utf-8 -*-
"""
测试全局阅读序位 helper 函数。
"""

from app.memory.chapter.sequence import (
    chapter_by_global_order,
    global_order_index,
    global_reading_sequence,
)
from app.storage.models.chapter import Chapter
from app.storage.models.volume import Volume


def _make_chapter(chapter_id: str, volume_id: str, order: int) -> Chapter:
    return Chapter(
        id=chapter_id,
        project_id="project-1",
        volume_id=volume_id,
        title=f"Chapter {chapter_id}",
        content="",
        order=order,
    )


def _make_volume(volume_id: str, order: int) -> Volume:
    return Volume(
        id=volume_id,
        project_id="project-1",
        title=f"Volume {volume_id}",
        order=order,
    )


class TestGlobalReadingSequence:
    """测试 global_reading_sequence 排序行为。"""

    def test_single_volume_yields_enumerated_order(self) -> None:
        volumes = [_make_volume("v1", 1)]
        chapters = [
            _make_chapter("c1", "v1", 1),
            _make_chapter("c2", "v1", 2),
            _make_chapter("c3", "v1", 3),
        ]

        result = global_reading_sequence(chapters, volumes)

        assert result == [(1, chapters[0]), (2, chapters[1]), (3, chapters[2])]

    def test_multi_volume_mixed_chapter_orders(self) -> None:
        volumes = [
            _make_volume("v1", 1),
            _make_volume("v2", 2),
        ]
        chapters = [
            _make_chapter("c1", "v1", 2),
            _make_chapter("c2", "v1", 1),
            _make_chapter("c3", "v2", 1),
            _make_chapter("c4", "v2", 3),
            _make_chapter("c5", "v2", 2),
        ]

        result = global_reading_sequence(chapters, volumes)

        order_ids = [c.id for _, c in result]
        assert order_ids == ["c2", "c1", "c3", "c5", "c4"]
        global_orders = [g for g, _ in result]
        assert global_orders == [1, 2, 3, 4, 5]

    def test_volume_not_found_treated_as_max_order(self) -> None:
        volumes = [_make_volume("v1", 1)]
        chapters = [
            _make_chapter("c1", "v1", 1),
            _make_chapter("c2", "v_missing", 1),
            _make_chapter("c3", "v1", 2),
        ]

        result = global_reading_sequence(chapters, volumes)

        order_ids = [c.id for _, c in result]
        assert order_ids == ["c1", "c3", "c2"]

    def test_volume_not_found_zero_volumes(self) -> None:
        chapters = [
            _make_chapter("c1", "v_missing", 1),
            _make_chapter("c2", "v_missing", 2),
        ]

        result = global_reading_sequence(chapters, [])

        assert len(result) == 2
        assert result[0][0] == 1
        assert result[1][0] == 2

    def test_empty_lists(self) -> None:
        assert global_reading_sequence([], []) == []
        assert global_reading_sequence([], [_make_volume("v1", 1)]) == []


class TestGlobalOrderIndex:
    """测试 global_order_index。"""

    def test_returns_mapping_from_ids(self) -> None:
        volumes = [
            _make_volume("v1", 1),
            _make_volume("v2", 2),
        ]
        chapters = [
            _make_chapter("c1", "v1", 1),
            _make_chapter("c2", "v2", 1),
        ]

        result = global_order_index(chapters, volumes)

        assert result == {"c1": 1, "c2": 2}

    def test_empty_chapters_returns_empty_dict(self) -> None:
        assert global_order_index([], []) == {}


class TestChapterByGlobalOrder:
    """测试 chapter_by_global_order。"""

    def test_returns_inverse_mapping(self) -> None:
        volumes = [
            _make_volume("v1", 1),
            _make_volume("v2", 2),
        ]
        chapters = [
            _make_chapter("c1", "v1", 1),
            _make_chapter("c2", "v2", 1),
        ]

        result = chapter_by_global_order(chapters, volumes)

        assert result == {1: chapters[0], 2: chapters[1]}

    def test_empty_chapters_returns_empty_dict(self) -> None:
        assert chapter_by_global_order([], []) == {}


class TestConsistency:
    """测试三个函数间的一致性。"""

    def test_index_and_by_order_are_inverse(self) -> None:
        volumes = [_make_volume("v1", 1), _make_volume("v2", 2)]
        chapters = [
            _make_chapter("c1", "v1", 1),
            _make_chapter("c2", "v1", 2),
            _make_chapter("c3", "v2", 1),
        ]

        idx = global_order_index(chapters, volumes)
        by_order = chapter_by_global_order(chapters, volumes)

        for chapter_id, global_ord in idx.items():
            assert by_order[global_ord].id == chapter_id
        for global_ord, chapter in by_order.items():
            assert idx[chapter.id] == global_ord

    def test_all_three_agree(self) -> None:
        volumes = [
            _make_volume("v1", 1),
            _make_volume("v2", 3),
            _make_volume("v3", 2),
        ]
        chapters = [
            _make_chapter("c1", "v1", 2),
            _make_chapter("c2", "v1", 1),
            _make_chapter("c3", "v2", 1),
            _make_chapter("c4", "v3", 3),
            _make_chapter("c5", "v3", 1),
            _make_chapter("c6", "v3", 2),
        ]

        seq = global_reading_sequence(chapters, volumes)
        idx = global_order_index(chapters, volumes)
        by_order = chapter_by_global_order(chapters, volumes)

        for global_ord, chapter in seq:
            assert idx[chapter.id] == global_ord
            assert by_order[global_ord] is chapter
