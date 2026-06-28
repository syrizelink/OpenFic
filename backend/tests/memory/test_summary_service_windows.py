# -*- coding: utf-8 -*-
"""
测试 summary_service 窗口/区间逻辑基于全局阅读序位的行为。
"""

from app.memory.chapter.summary_service import (
    LONG_TERM_SUMMARY_INTERVAL,
    _fixed_summary_windows,
    _source_chapter_summary_signatures,
    build_long_term_summary_window,
    encode_summary_list,
    is_long_term_summary_stale,
    list_eligible_long_term_ranges,
    list_ready_unaggregated_long_term_windows,
)
from app.storage.models.chapter import Chapter
from app.storage.models.chapter_summary import ChapterSummary
from app.storage.models.volume import Volume
from app.storage.repos.chapter_summary_repo import (
    SUMMARY_STATUS_READY,
    SUMMARY_TYPE_CHAPTER,
    SUMMARY_TYPE_LONG_TERM,
)


def _make_volume(volume_id: str, order: int) -> Volume:
    return Volume(
        id=volume_id,
        project_id="project-1",
        title=f"Volume {volume_id}",
        order=order,
    )


def _make_chapter(
    chapter_id: str,
    volume_id: str,
    order: int,
    *,
    word_count: int = 1000,
    content: str = "正文内容",
) -> Chapter:
    return Chapter(
        id=chapter_id,
        project_id="project-1",
        volume_id=volume_id,
        title=f"Chapter {chapter_id}",
        content=content,
        order=order,
        word_count=word_count,
    )


def _make_chapter_summary(
    chapter: Chapter,
    global_order: int,
    *,
    status: str = SUMMARY_STATUS_READY,
) -> ChapterSummary:
    return ChapterSummary(
        id=f"summary-{chapter.id}",
        project_id="project-1",
        summary_type=SUMMARY_TYPE_CHAPTER,
        status=status,
        chapter_id=chapter.id,
        volume_id=chapter.volume_id,
        chapter_order=global_order,
        start_order=global_order,
        end_order=global_order,
        summary=f"摘要 {chapter.id}",
        source_content_normalized=chapter.content,
    )


def _build_two_volume_setup(chapters_per_volume: int = 5) -> tuple[list[Volume], list[Chapter]]:
    volumes = [_make_volume("v1", 1), _make_volume("v2", 2)]
    chapters: list[Chapter] = []
    for v_idx, volume in enumerate(volumes):
        for o in range(1, chapters_per_volume + 1):
            chapters.append(_make_chapter(f"c{v_idx + 1}_{o}", volume.id, o))
    return volumes, chapters


class TestFixedSummaryWindows:
    """测试 _fixed_summary_windows 基于全局序位切窗。"""

    def test_cross_volume_window_includes_all_chapters(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        windows = _fixed_summary_windows(chapters, volumes, LONG_TERM_SUMMARY_INTERVAL)

        assert len(windows) == 1
        window = windows[0]
        assert len(window) == 10
        assert [c.id for c in window] == [
            "c1_1", "c1_2", "c1_3", "c1_4", "c1_5",
            "c2_1", "c2_2", "c2_3", "c2_4", "c2_5",
        ]

    def test_multiple_windows_across_volumes(self) -> None:
        volumes = [_make_volume("v1", 1), _make_volume("v2", 2)]
        chapters: list[Chapter] = []
        for v_idx, volume in enumerate(volumes):
            for o in range(1, 11):
                chapters.append(_make_chapter(f"c{v_idx + 1}_{o}", volume.id, o))

        windows = _fixed_summary_windows(chapters, volumes, LONG_TERM_SUMMARY_INTERVAL)

        assert len(windows) == 2
        assert [c.id for c in windows[0]] == [f"c1_{o}" for o in range(1, 11)]
        assert [c.id for c in windows[1]] == [f"c2_{o}" for o in range(1, 11)]

    def test_window_splits_at_volume_boundary(self) -> None:
        volumes = [_make_volume("v1", 1), _make_volume("v2", 2)]
        chapters = [
            _make_chapter("c1_1", "v1", 1),
            _make_chapter("c1_2", "v1", 2),
            _make_chapter("c1_3", "v1", 3),
            _make_chapter("c2_1", "v2", 1),
            _make_chapter("c2_2", "v2", 2),
            _make_chapter("c2_3", "v2", 3),
            _make_chapter("c2_4", "v2", 4),
            _make_chapter("c2_5", "v2", 5),
            _make_chapter("c2_6", "v2", 6),
            _make_chapter("c2_7", "v2", 7),
        ]
        windows = _fixed_summary_windows(chapters, volumes, LONG_TERM_SUMMARY_INTERVAL)

        assert len(windows) == 1
        window_ids = [c.id for c in windows[0]]
        assert window_ids == [
            "c1_1", "c1_2", "c1_3",
            "c2_1", "c2_2", "c2_3", "c2_4", "c2_5", "c2_6", "c2_7",
        ]


class TestBuildLongTermSummaryWindow:
    """测试 build_long_term_summary_window 基于全局序位。"""

    def test_window_spans_two_volumes(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        global_order = {ch.id: i for i, ch in enumerate(chapters, 1)}
        summaries = [_make_chapter_summary(ch, global_order[ch.id]) for ch in chapters]

        window = build_long_term_summary_window(chapters, volumes, summaries, 1, 10)

        assert window is not None
        assert window.start_order == 1
        assert window.end_order == 10
        assert len(window.chapter_ids) == 10
        assert window.source_summaries[0].chapter_id == "c1_1"
        assert window.source_summaries[-1].chapter_id == "c2_5"

    def test_window_returns_none_when_missing_summary(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        global_order = {ch.id: i for i, ch in enumerate(chapters, 1)}
        summaries = [_make_chapter_summary(ch, global_order[ch.id]) for ch in chapters]
        summaries[5].status = "not_generated"

        window = build_long_term_summary_window(chapters, volumes, summaries, 1, 10)

        assert window is None

    def test_window_returns_none_when_range_exceeds_chapters(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        global_order = {ch.id: i for i, ch in enumerate(chapters, 1)}
        summaries = [_make_chapter_summary(ch, global_order[ch.id]) for ch in chapters]

        window = build_long_term_summary_window(chapters, volumes, summaries, 1, 11)

        assert window is None

    def test_window_excludes_skipped_chapter_from_sources(self) -> None:
        volumes = [_make_volume("v1", 1), _make_volume("v2", 2)]
        chapters = [_make_chapter(f"c{i}", f"v{(i - 1) // 5 + 1}", (i - 1) % 5 + 1) for i in range(1, 11)]
        chapters[0] = _make_chapter("c1", "v1", 1, word_count=100)
        global_order = {ch.id: i for i, ch in enumerate(chapters, 1)}
        summaries = [_make_chapter_summary(ch, global_order[ch.id]) for ch in chapters[1:]]

        window = build_long_term_summary_window(chapters, volumes, summaries, 1, 10)

        assert window is not None
        assert len(window.source_summaries) == 9
        assert all(summary.chapter_id != "c1" for summary in window.source_summaries)


class TestListEligibleLongTermRanges:
    """测试 list_eligible_long_term_ranges 基于全局序位。"""

    def test_returns_global_ranges_cross_volume(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        global_order = {ch.id: i for i, ch in enumerate(chapters, 1)}
        summaries = [_make_chapter_summary(ch, global_order[ch.id]) for ch in chapters]

        ranges = list_eligible_long_term_ranges(chapters, volumes, summaries)

        assert ranges == [(1, 10)]

    def test_returns_empty_when_summaries_not_ready(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        global_order = {ch.id: i for i, ch in enumerate(chapters, 1)}
        summaries = [_make_chapter_summary(ch, global_order[ch.id], status="queued") for ch in chapters]

        ranges = list_eligible_long_term_ranges(chapters, volumes, summaries)

        assert ranges == []


class TestIsLongTermSummaryStale:
    """测试 is_long_term_summary_stale 基于全局序位。"""

    def test_not_stale_when_matching(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        global_order = {ch.id: i for i, ch in enumerate(chapters, 1)}
        summaries = [_make_chapter_summary(ch, global_order[ch.id]) for ch in chapters]

        long_term = ChapterSummary(
            id="lt-1",
            project_id="project-1",
            summary_type=SUMMARY_TYPE_LONG_TERM,
            status=SUMMARY_STATUS_READY,
            start_order=1,
            end_order=10,
            source_chapter_ids_json=encode_summary_list([ch.id for ch in chapters]),
            source_chapter_summary_signatures_json=encode_summary_list(
                _source_chapter_summary_signatures(summaries)
            ),
        )

        assert is_long_term_summary_stale(long_term, chapters, summaries, volumes) is False

    def test_stale_when_source_chapter_ids_differ(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        global_order = {ch.id: i for i, ch in enumerate(chapters, 1)}
        summaries = [_make_chapter_summary(ch, global_order[ch.id]) for ch in chapters]

        long_term = ChapterSummary(
            id="lt-1",
            project_id="project-1",
            summary_type=SUMMARY_TYPE_LONG_TERM,
            status=SUMMARY_STATUS_READY,
            start_order=1,
            end_order=10,
            source_chapter_ids_json=encode_summary_list(["wrong_id"]),
            source_chapter_summary_signatures_json=encode_summary_list(
                [s.id for s in summaries]
            ),
        )

        assert is_long_term_summary_stale(long_term, chapters, summaries, volumes) is True

    def test_stale_when_none_summary(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)

        assert is_long_term_summary_stale(None, chapters, [], volumes) is False

    def test_stale_when_orders_missing(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        long_term = ChapterSummary(
            id="lt-1",
            project_id="project-1",
            summary_type=SUMMARY_TYPE_LONG_TERM,
            status=SUMMARY_STATUS_READY,
            start_order=None,
            end_order=None,
        )

        assert is_long_term_summary_stale(long_term, chapters, [], volumes) is True


class TestListReadyUnaggregatedLongTermWindows:
    """测试 list_ready_unaggregated_long_term_windows 基于全局序位。"""

    def test_returns_window_when_no_existing_long_term(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        global_order = {ch.id: i for i, ch in enumerate(chapters, 1)}
        summaries = [_make_chapter_summary(ch, global_order[ch.id]) for ch in chapters]

        windows = list_ready_unaggregated_long_term_windows(chapters, volumes, summaries, [])

        assert len(windows) == 1
        assert windows[0].start_order == 1
        assert windows[0].end_order == 10

    def test_skips_existing_fresh_long_term(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        global_order = {ch.id: i for i, ch in enumerate(chapters, 1)}
        summaries = [_make_chapter_summary(ch, global_order[ch.id]) for ch in chapters]

        long_term = ChapterSummary(
            id="lt-1",
            project_id="project-1",
            summary_type=SUMMARY_TYPE_LONG_TERM,
            status=SUMMARY_STATUS_READY,
            start_order=1,
            end_order=10,
            source_chapter_ids_json=encode_summary_list([ch.id for ch in chapters]),
            source_chapter_summary_signatures_json=encode_summary_list(
                _source_chapter_summary_signatures(summaries)
            ),
        )

        windows = list_ready_unaggregated_long_term_windows(
            chapters, volumes, summaries, [long_term]
        )

        assert windows == []

    def test_returns_window_when_existing_is_stale(self) -> None:
        volumes, chapters = _build_two_volume_setup(5)
        global_order = {ch.id: i for i, ch in enumerate(chapters, 1)}
        summaries = [_make_chapter_summary(ch, global_order[ch.id]) for ch in chapters]

        long_term = ChapterSummary(
            id="lt-1",
            project_id="project-1",
            summary_type=SUMMARY_TYPE_LONG_TERM,
            status=SUMMARY_STATUS_READY,
            start_order=1,
            end_order=10,
            source_chapter_ids_json=encode_summary_list(["wrong_id"]),
            source_chapter_summary_signatures_json=encode_summary_list([]),
        )

        windows = list_ready_unaggregated_long_term_windows(
            chapters, volumes, summaries, [long_term]
        )

        assert len(windows) == 1
        assert windows[0].start_order == 1
        assert windows[0].end_order == 10
