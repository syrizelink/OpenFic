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
async def test_list_characters_returns_project_character_names() -> None:
    from app.agent_runtime.tools.impls.context.character import ListCharactersTool

    tool = ListCharactersTool(_state=_make_state())
    characters = [
        SimpleNamespace(id="char-1", name="林舟", description="主角", is_favorited=True),
        SimpleNamespace(id="char-2", name="沈墨", description="反派", is_favorited=False),
    ]

    with patch(
        "app.agent_runtime.tools.impls.context.character.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.character.character_repo"
    ) as mock_character_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_character_repo.list_by_project = AsyncMock(return_value=(characters, 2))

        result = await tool.ainvoke({})

    assert json.loads(result) == {
        "characters": [
            {"name": "林舟"},
            {"name": "沈墨"},
        ]
    }


@pytest.mark.asyncio
async def test_read_character_reads_description_by_name() -> None:
    from app.agent_runtime.tools.impls.context.character import ReadCharacterTool

    tool = ReadCharacterTool(_state=_make_state())
    characters = [
        SimpleNamespace(
            id="char-1",
            name="林舟",
            description="主角\n旧友",
            is_favorited=True,
        ),
    ]

    with patch(
        "app.agent_runtime.tools.impls.context.character.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.character.character_repo"
    ) as mock_character_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_character_repo.list_by_project = AsyncMock(return_value=(characters, 1))

        result = await tool.ainvoke({"name": "林舟"})

    assert json.loads(result) == {
        "name": "林舟",
        "description": "1|主角\n2|旧友",
    }


@pytest.mark.asyncio
async def test_create_character_returns_diff() -> None:
    from app.agent_runtime.tools.impls.context.character import CreateCharacterTool

    tool = CreateCharacterTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    created = SimpleNamespace(
        id="char-1",
        project_id="proj-1",
        name="林舟",
        description="主角",
        image_path=None,
        is_favorited=False,
    )

    with patch(
        "app.agent_runtime.tools.impls.context.character.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.character.character_repo"
    ) as mock_character_repo, patch(
        "app.agent_runtime.tools.impls.context.character.character_service"
    ) as mock_character_service, patch(
        "app.agent_runtime.tools.impls.context.character.record_character_diffs"
    ) as mock_record_diffs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_character_repo.list_by_project = AsyncMock(return_value=([], 0))
        mock_character_service.create_character = AsyncMock(return_value=created)
        mock_record_diffs.return_value = ["char-1"]

        result = await tool.ainvoke({"name": "林舟", "description": "主角"})

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["character_diff"] == {
        "operation": "create",
        "character_id": "char-1",
        "character_name": "林舟",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "主角",
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_edit_character_replaces_description_text() -> None:
    from app.agent_runtime.tools.impls.context.character import EditCharacterTool

    tool = EditCharacterTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    character = SimpleNamespace(
        id="char-1",
        project_id="proj-1",
        name="林舟",
        description="主角",
        is_favorited=False,
    )
    updated_character = SimpleNamespace(
        id="char-1",
        project_id="proj-1",
        name="林舟",
        description="主角与旧友",
        is_favorited=True,
    )

    with patch(
        "app.agent_runtime.tools.impls.context.character.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.character.character_repo"
    ) as mock_character_repo, patch(
        "app.agent_runtime.tools.impls.context.character.character_service"
    ) as mock_character_service, patch(
        "app.agent_runtime.tools.impls.context.character.record_character_diffs"
    ) as mock_record_diffs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_character_repo.list_by_project = AsyncMock(return_value=([character], 1))
        mock_character_service.update_character = AsyncMock(return_value=updated_character)
        mock_record_diffs.return_value = ["char-1"]

        result = await tool.ainvoke(
            {
                "name": "林舟",
                "old_description": "主角",
                "new_description": "主角与旧友",
            }
        )

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["character_diff"]["operation"] == "edit"
    assert data["metadata"]["character_diff"]["sections"][0]["lines"] == [
        {
            "type": "removed",
            "before_line_number": 1,
            "after_line_number": None,
            "text": "主角",
        },
        {
            "type": "added",
            "before_line_number": None,
            "after_line_number": 1,
            "text": "主角与旧友",
        },
    ]


@pytest.mark.asyncio
async def test_delete_character_removes_name() -> None:
    from app.agent_runtime.tools.impls.context.character import DeleteCharacterTool

    tool = DeleteCharacterTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    character = SimpleNamespace(
        id="char-1",
        project_id="proj-1",
        name="林舟",
        description="主角",
        is_favorited=False,
    )

    with patch(
        "app.agent_runtime.tools.impls.context.character.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.character.character_repo"
    ) as mock_character_repo, patch(
        "app.agent_runtime.tools.impls.context.character.character_service"
    ) as mock_character_service, patch(
        "app.agent_runtime.tools.impls.context.character.record_character_diffs"
    ) as mock_record_diffs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_character_repo.list_by_project = AsyncMock(return_value=([character], 1))
        mock_character_service.delete_character = AsyncMock(return_value=None)
        mock_record_diffs.return_value = ["char-1"]

        result = await tool.ainvoke({"name": "林舟"})

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["character_diff"]["operation"] == "delete"
    assert data["metadata"]["character_diff"]["character_id"] == "char-1"
    assert data["metadata"]["character_diff"]["character_name"] == "林舟"


@pytest.mark.asyncio
async def test_list_world_entries_returns_enabled_entry_titles() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import ListWorldEntriesTool

    tool = ListWorldEntriesTool(_state=_make_state())
    entries = [
        SimpleNamespace(id="e1", name="主角", uid=1, order=1, content="林舟"),
        SimpleNamespace(id="e2", name="势力", uid=2, order=2, content="青岚会"),
    ]

    with patch(
        "app.agent_runtime.tools.impls.context.world_entry.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_repo"
    ) as mock_world_repo, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo"
    ) as mock_entry_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_world_repo.get_by_project_id = AsyncMock(return_value=SimpleNamespace(id="world-1"))
        mock_entry_repo.list_enabled_by_world_info = AsyncMock(return_value=entries)

        result = await tool.ainvoke({})

    assert json.loads(result) == {
        "entries": [
            {"title": "主角", "uid": 1, "order": 1},
            {"title": "势力", "uid": 2, "order": 2},
        ]
    }


@pytest.mark.asyncio
async def test_read_world_entry_reads_content_by_title() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import ReadWorldEntryTool

    tool = ReadWorldEntryTool(_state=_make_state())
    entries = [
        SimpleNamespace(id="e1", name="主角", uid=1, order=1, content="林舟\n旧友"),
    ]

    with patch(
        "app.agent_runtime.tools.impls.context.world_entry.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_repo"
    ) as mock_world_repo, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo"
    ) as mock_entry_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_world_repo.get_by_project_id = AsyncMock(return_value=SimpleNamespace(id="world-1"))
        mock_entry_repo.list_by_world_info = AsyncMock(return_value=entries)

        result = await tool.ainvoke({"title": "主角"})

    assert json.loads(result) == {
        "title": "主角",
        "uid": 1,
        "order": 1,
        "content": "1|林舟\n2|旧友",
    }


@pytest.mark.asyncio
async def test_read_world_entry_rejects_duplicate_titles() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import ReadWorldEntryTool

    tool = ReadWorldEntryTool(_state=_make_state())
    entries = [
        SimpleNamespace(id="e1", name="主角", uid=1, order=1, content="一"),
        SimpleNamespace(id="e2", name="主角", uid=2, order=2, content="二"),
    ]

    with patch(
        "app.agent_runtime.tools.impls.context.world_entry.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_repo"
    ) as mock_world_repo, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo"
    ) as mock_entry_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_world_repo.get_by_project_id = AsyncMock(return_value=SimpleNamespace(id="world-1"))
        mock_entry_repo.list_by_world_info = AsyncMock(return_value=entries)

        result = await tool.ainvoke({"title": "主角"})

    assert json.loads(result) == {"error": "世界书条目标题不唯一: 主角"}


@pytest.mark.asyncio
async def test_create_world_entry_returns_diff() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import CreateWorldEntryTool

    tool = CreateWorldEntryTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    created = SimpleNamespace(
        id="e1",
        world_info_id="world-1",
        name="主角",
        uid=1,
        order=1,
        content="林舟",
        token_count=2,
        is_enabled=True,
    )

    with patch(
        "app.agent_runtime.tools.impls.context.world_entry.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_repo"
    ) as mock_world_repo, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo"
    ) as mock_entry_repo, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_service"
    ) as mock_entry_service, patch(
        "app.agent_runtime.tools.impls.context.world_entry.record_world_entry_diffs"
    ) as mock_record_diffs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_world_repo.get_by_project_id = AsyncMock(return_value=SimpleNamespace(id="world-1"))
        mock_entry_repo.list_by_world_info = AsyncMock(return_value=[])
        mock_entry_service.create_entry = AsyncMock(return_value=created)
        mock_record_diffs.return_value = ["e1"]

        result = await tool.ainvoke({"title": "主角", "content": "林舟"})

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["world_info_id"] == "world-1"
    assert data["metadata"]["world_entry_diff"] == {
        "operation": "create",
        "entry_id": "e1",
        "entry_title": "主角",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "林舟",
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_create_world_entry_rejects_duplicate_title() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import CreateWorldEntryTool

    tool = CreateWorldEntryTool(_state={**_make_state(), "current_revision_id": "rev-1"})

    with patch(
        "app.agent_runtime.tools.impls.context.world_entry.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_repo"
    ) as mock_world_repo, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo"
    ) as mock_entry_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_world_repo.get_by_project_id = AsyncMock(return_value=SimpleNamespace(id="world-1"))
        mock_entry_repo.list_by_world_info = AsyncMock(
            return_value=[SimpleNamespace(id="e1", name="主角", uid=1, order=1, content="")]
        )

        result = await tool.ainvoke({"title": "主角", "content": "林舟"})

    assert json.loads(result) == {"error": "世界书条目标题已存在: 主角"}


@pytest.mark.asyncio
async def test_edit_world_entry_returns_diff() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import EditWorldEntryTool

    tool = EditWorldEntryTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    entry = SimpleNamespace(
        id="e1",
        world_info_id="world-1",
        name="主角",
        uid=1,
        order=1,
        content="林舟",
        token_count=2,
        is_enabled=True,
    )
    updated_entry = SimpleNamespace(
        id="e1",
        world_info_id="world-1",
        name="主角",
        uid=1,
        order=1,
        content="林舟与旧友",
        token_count=2,
        is_enabled=True,
    )

    with patch(
        "app.agent_runtime.tools.impls.context.world_entry.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_repo"
    ) as mock_world_repo, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo"
    ) as mock_entry_repo, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_service"
    ) as mock_entry_service, patch(
        "app.agent_runtime.tools.impls.context.world_entry.record_world_entry_diffs"
    ) as mock_record_diffs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_world_repo.get_by_project_id = AsyncMock(return_value=SimpleNamespace(id="world-1"))
        mock_entry_repo.list_by_world_info = AsyncMock(return_value=[entry])
        mock_entry_service.update_entry = AsyncMock(return_value=updated_entry)
        mock_record_diffs.return_value = ["e1"]

        result = await tool.ainvoke(
            {"title": "主角", "old_content": "林舟", "new_content": "林舟与旧友"}
        )

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["world_entry_diff"]["operation"] == "edit"
    assert data["metadata"]["world_entry_diff"]["sections"] == [
        {
            "type": "content",
            "lines": [
                {
                    "type": "removed",
                    "before_line_number": 1,
                    "after_line_number": None,
                    "text": "林舟",
                },
                {
                    "type": "added",
                    "before_line_number": None,
                    "after_line_number": 1,
                    "text": "林舟与旧友",
                },
            ],
        }
    ]


@pytest.mark.asyncio
async def test_edit_world_entry_rejects_duplicate_new_title() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import EditWorldEntryTool

    tool = EditWorldEntryTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    entries = [
        SimpleNamespace(id="e1", name="主角", uid=1, order=1, content="林舟"),
        SimpleNamespace(id="e2", name="反派", uid=2, order=2, content="沈墨"),
    ]

    with patch(
        "app.agent_runtime.tools.impls.context.world_entry.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_repo"
    ) as mock_world_repo, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo"
    ) as mock_entry_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_world_repo.get_by_project_id = AsyncMock(return_value=SimpleNamespace(id="world-1"))
        mock_entry_repo.list_by_world_info = AsyncMock(return_value=entries)

        result = await tool.ainvoke({"title": "主角", "new_title": "反派"})

    assert json.loads(result) == {"error": "世界书条目标题已存在: 反派"}


@pytest.mark.asyncio
async def test_delete_world_entry_removes_title() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import DeleteWorldEntryTool

    tool = DeleteWorldEntryTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    entry = SimpleNamespace(
        id="e1",
        world_info_id="world-1",
        name="主角",
        uid=1,
        order=1,
        content="林舟",
        token_count=2,
        is_enabled=True,
    )

    with patch(
        "app.agent_runtime.tools.impls.context.world_entry.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_repo"
    ) as mock_world_repo, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo"
    ) as mock_entry_repo, patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_service"
    ) as mock_entry_service, patch(
        "app.agent_runtime.tools.impls.context.world_entry.record_world_entry_diffs"
    ) as mock_record_diffs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_world_repo.get_by_project_id = AsyncMock(return_value=SimpleNamespace(id="world-1"))
        mock_entry_repo.list_by_world_info = AsyncMock(return_value=[entry])
        mock_entry_service.delete_entry = AsyncMock(return_value=None)
        mock_record_diffs.return_value = ["e1"]

        result = await tool.ainvoke({"title": "主角"})

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["world_info_id"] == "world-1"
    assert data["metadata"]["world_entry_diff"]["operation"] == "delete"
    assert data["metadata"]["world_entry_diff"]["entry_id"] == "e1"
    assert data["metadata"]["world_entry_diff"]["entry_title"] == "主角"
