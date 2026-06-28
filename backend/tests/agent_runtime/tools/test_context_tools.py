import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _make_state() -> dict:
    return {
        "session_id": "sess-1",
        "project_id": "proj-1",
        "model_config": {},
        "active_agent": "writer",
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "message_checkpoints": [],
        "user_request": "",
    }


@pytest.mark.asyncio
async def test_read_chapter_summaries_reads_project_page() -> None:
    from app.agent_runtime.tools.impls.context.read_chapter_summaries import (
        ReadChapterSummariesTool,
    )

    tool = ReadChapterSummariesTool(_state=_make_state())
    chapters = [
        SimpleNamespace(id="c2", order=2, title="第二章"),
        SimpleNamespace(id="c3", order=3, title="第三章"),
    ]
    summaries = [
        SimpleNamespace(chapter_id="c2", summary="第二章摘要"),
        SimpleNamespace(chapter_id="c3", summary="第三章摘要"),
    ]

    with patch(
        "app.agent_runtime.tools.impls.context.read_chapter_summaries.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.read_chapter_summaries.chapter_repo"
    ) as mock_chapter_repo, patch(
        "app.agent_runtime.tools.impls.context.read_chapter_summaries.chapter_summary_repo"
    ) as mock_summary_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_chapter_repo.list_by_project_page = AsyncMock(return_value=chapters)
        mock_summary_repo.list_chapter_summaries_by_chapter_ids = AsyncMock(
            return_value=summaries
        )

        result = await tool.ainvoke({"offset": 1, "limit": 2})

    assert json.loads(result) == {
        "summaries": [
            {"order": 2, "title": "第二章", "summary": "第二章摘要"},
            {"order": 3, "title": "第三章", "summary": "第三章摘要"},
        ]
    }


@pytest.mark.asyncio
async def test_read_chapter_summaries_prefers_page_query_over_orders() -> None:
    from app.agent_runtime.tools.impls.context.read_chapter_summaries import (
        ReadChapterSummariesTool,
    )

    tool = ReadChapterSummariesTool(_state=_make_state())
    chapters = [SimpleNamespace(id="c4", order=4, title="第四章")]
    summaries = [SimpleNamespace(chapter_id="c4", summary="第四章摘要")]

    with patch(
        "app.agent_runtime.tools.impls.context.read_chapter_summaries.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.read_chapter_summaries.chapter_repo"
    ) as mock_chapter_repo, patch(
        "app.agent_runtime.tools.impls.context.read_chapter_summaries.chapter_summary_repo"
    ) as mock_summary_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_chapter_repo.list_by_project_page = AsyncMock(return_value=chapters)
        mock_chapter_repo.list_by_project = AsyncMock()
        mock_summary_repo.list_chapter_summaries_by_chapter_ids = AsyncMock(
            return_value=summaries
        )

        result = await tool.ainvoke({"offset": 0, "limit": 1, "orders": [9, 7]})

    assert json.loads(result) == {
        "summaries": [
            {"order": 4, "title": "第四章", "summary": "第四章摘要"},
        ]
    }
    mock_chapter_repo.list_by_project.assert_not_called()


@pytest.mark.asyncio
async def test_read_chapter_summaries_reads_exact_orders_when_requested() -> None:
    from app.agent_runtime.tools.impls.context.read_chapter_summaries import (
        ReadChapterSummariesTool,
    )

    tool = ReadChapterSummariesTool(_state=_make_state())
    chapters = [
        SimpleNamespace(id="c2", order=2, title="第二章"),
        SimpleNamespace(id="c5", order=5, title="第五章"),
    ]
    summaries = [
        SimpleNamespace(chapter_id="c5", summary="第五章摘要"),
        SimpleNamespace(chapter_id="c2", summary="第二章摘要"),
    ]

    with patch(
        "app.agent_runtime.tools.impls.context.read_chapter_summaries.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.read_chapter_summaries.chapter_repo"
    ) as mock_chapter_repo, patch(
        "app.agent_runtime.tools.impls.context.read_chapter_summaries.chapter_summary_repo"
    ) as mock_summary_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_chapter_repo.list_by_project = AsyncMock(return_value=chapters)
        mock_summary_repo.list_chapter_summaries_by_chapter_ids = AsyncMock(
            return_value=summaries
        )

        result = await tool.ainvoke({"orders": [5, 2]})

    assert json.loads(result) == {
        "summaries": [
            {"order": 5, "title": "第五章", "summary": "第五章摘要"},
            {"order": 2, "title": "第二章", "summary": "第二章摘要"},
        ]
    }


@pytest.mark.asyncio
async def test_read_range_summaries_returns_ascending_page() -> None:
    from app.agent_runtime.tools.impls.context.read_range_summaries import (
        ReadRangeSummariesTool,
    )

    tool = ReadRangeSummariesTool(_state=_make_state())
    summaries = [
        SimpleNamespace(start_order=21, end_order=30, summary="21-30"),
        SimpleNamespace(start_order=11, end_order=20, summary="11-20"),
        SimpleNamespace(start_order=1, end_order=10, summary="1-10"),
    ]

    with patch(
        "app.agent_runtime.tools.impls.context.read_range_summaries.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.read_range_summaries.chapter_summary_repo"
    ) as mock_summary_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_summary_repo.list_long_term_summaries_by_project = AsyncMock(
            return_value=summaries
        )

        result = await tool.ainvoke({"offset": 1, "limit": 2})

    assert json.loads(result) == {
        "summaries": [
            {"start_order": 11, "end_order": 20, "summary": "11-20"},
            {"start_order": 21, "end_order": 30, "summary": "21-30"},
        ]
    }


@pytest.mark.asyncio
async def test_read_world_info_injects_all_enabled_entries() -> None:
    from app.agent_runtime.tools.impls.context.read_world_info import ReadWorldInfoTool

    tool = ReadWorldInfoTool(_state=_make_state())
    entries = [
        SimpleNamespace(
            id="e2",
            name="势力",
            order=2,
            content="青岚会",
        ),
        SimpleNamespace(
            id="e1",
            name="主角",
            order=1,
            content="林舟 & 旧友",
        ),
        SimpleNamespace(
            id="e3",
            name="无关",
            order=3,
            content="不会出现",
        ),
    ]

    with patch(
        "app.agent_runtime.tools.impls.context.read_world_info.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.read_world_info.world_info_repo"
    ) as mock_world_repo, patch(
        "app.agent_runtime.tools.impls.context.read_world_info.world_info_entry_repo"
    ) as mock_entry_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_world_repo.get_by_project_id = AsyncMock(
            return_value=SimpleNamespace(id="world-1")
        )
        mock_entry_repo.list_enabled_by_world_info = AsyncMock(return_value=entries)

        result = await tool.ainvoke({})

    assert json.loads(result) == {
        "content": "<主角>\n林舟 &amp; 旧友\n</主角>\n<势力>\n青岚会\n</势力>\n<无关>\n不会出现\n</无关>"
    }
