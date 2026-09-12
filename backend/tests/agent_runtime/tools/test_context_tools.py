import asyncio
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
        SimpleNamespace(id="c2", order=2, title="Bab 2"),
        SimpleNamespace(id="c3", order=3, title="Bab 3"),
    ]
    summaries = [
        SimpleNamespace(chapter_id="c2", summary="Ringkasan Bab 2"),
        SimpleNamespace(chapter_id="c3", summary="Ringkasan Bab 3"),
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
            {"order": 2, "title": "Bab 2", "summary": "Ringkasan Bab 2"},
            {"order": 3, "title": "Bab 3", "summary": "Ringkasan Bab 3"},
        ]
    }


@pytest.mark.asyncio
async def test_read_chapter_summaries_prefers_page_query_over_orders() -> None:
    from app.agent_runtime.tools.impls.context.read_chapter_summaries import (
        ReadChapterSummariesTool,
    )

    tool = ReadChapterSummariesTool(_state=_make_state())
    chapters = [SimpleNamespace(id="c4", order=4, title="Bab 4")]
    summaries = [SimpleNamespace(chapter_id="c4", summary="Ringkasan Bab 4")]

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
            {"order": 4, "title": "Bab 4", "summary": "Ringkasan Bab 4"},
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
        SimpleNamespace(id="c2", order=2, title="Bab 2"),
        SimpleNamespace(id="c5", order=5, title="Bab 5"),
    ]
    summaries = [
        SimpleNamespace(chapter_id="c5", summary="Ringkasan Bab 5"),
        SimpleNamespace(chapter_id="c2", summary="Ringkasan Bab 2"),
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
            {"order": 5, "title": "Bab 5", "summary": "Ringkasan Bab 5"},
            {"order": 2, "title": "Bab 2", "summary": "Ringkasan Bab 2"},
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
        SimpleNamespace(id="char-1", name="Linu", description="Tokoh Utama", is_favorited=True),
        SimpleNamespace(id="char-2", name="Semmi", description="Antagonis", is_favorited=False),
    ]

    with patch(
        "app.agent_runtime.tools.impls.context.character.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.character.character_repo"
    ) as mock_character_repo:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        mock_character_repo.list_all_by_project = AsyncMock(return_value=characters)

        result = await tool.ainvoke({})

    assert json.loads(result) == {
        "characters": [
            {"name": "Linu"},
            {"name": "Semmi"},
        ]
    }


@pytest.mark.asyncio
async def test_read_character_reads_description_by_name() -> None:
    from app.agent_runtime.tools.impls.context.character import ReadCharacterTool

    tool = ReadCharacterTool(_state=_make_state())
    characters = [
        SimpleNamespace(
            id="char-1",
            name="Linu",
            description="Tokoh Utama\nkawan lama",
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
        mock_character_repo.list_all_by_project = AsyncMock(return_value=characters)

        result = await tool.ainvoke({"name": "Linu"})

    assert json.loads(result) == {
        "name": "Linu",
        "description": "1|Tokoh Utama\n2|kawan lama",
    }


@pytest.mark.asyncio
async def test_create_character_returns_diff() -> None:
    from app.agent_runtime.tools.impls.context.character import CreateCharacterTool

    tool = CreateCharacterTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    created = SimpleNamespace(
        id="char-1",
        project_id="proj-1",
        name="Linu",
        description="Tokoh Utama",
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
        mock_character_repo.list_all_by_project = AsyncMock(return_value=[])
        mock_character_service.create_character = AsyncMock(return_value=created)
        mock_record_diffs.return_value = ["char-1"]

        result = await tool.ainvoke({"name": "Linu", "description": "Tokoh Utama"})

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["character_diff"] == {
        "operation": "create",
        "character_id": "char-1",
        "character_name": "Linu",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "Tokoh Utama",
                    }
                ],
            }
        ],
    }


async def test_create_character_serializes_parallel_creates_per_project() -> None:
    from app.agent_runtime.tools.impls import _locks
    from app.agent_runtime.tools.impls.context import character as ch

    _locks._LOCKS.clear()
    entered = asyncio.Event()
    release = asyncio.Event()
    call_count = 0

    async def list_characters(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            entered.set()
            await release.wait()
        return []

    created = SimpleNamespace(id="char-1", project_id="proj-1", name="Linu", description="Tokoh Utama")
    ch_name = "app.agent_runtime.tools.impls.context.character"
    with patch(f"{ch_name}.create_session") as mock_cs, patch(
        f"{ch_name}.character_repo"
    ) as mock_repo, patch(
        f"{ch_name}.character_service"
    ) as mock_service, patch(
        f"{ch_name}.record_character_diffs", AsyncMock()
    ):
        mock_cs.return_value = AsyncMock()
        mock_repo.list_all_by_project = AsyncMock(side_effect=list_characters)
        mock_service.create_character = AsyncMock(return_value=created)

        def make_tool():
            return ch.CreateCharacterTool(
                _state={**_make_state(), "current_revision_id": "rev-1"}
            )

        task1 = asyncio.create_task(
            make_tool().ainvoke({"name": "Linu", "description": "Tokoh Utama"})
        )
        await entered.wait()
        task2 = asyncio.create_task(
            make_tool().ainvoke({"name": "Linu", "description": "Tokoh Utama"})
        )
        await asyncio.sleep(0.05)
        assert not task2.done()
        release.set()
        await asyncio.gather(task1, task2)


@pytest.mark.asyncio
async def test_create_character_rejects_over_limit_description_without_creating() -> None:
    from app.agent_runtime.tools.impls.context.character import CreateCharacterTool

    tool = CreateCharacterTool(_state={**_make_state(), "current_revision_id": "rev-1"})

    with patch(
        "app.agent_runtime.tools.impls.context.character.character_service"
    ) as mock_character_service:
        mock_character_service.create_character = AsyncMock()

        result = await tool.ainvoke(
            {"name": "Linu", "description": "\n".join("Isi" for _ in range(2001))}
        )

    assert "Konten melebihi batas" in json.loads(result)["message"]
    mock_character_service.create_character.assert_not_awaited()


def test_edit_character_input_rejects_empty_old_description() -> None:
    from pydantic import ValidationError

    from app.agent_runtime.tools.impls.context.character import EditCharacterInput

    with pytest.raises(ValidationError):
        EditCharacterInput.model_validate({
            "name": "Linu",
            "old_description": "",
            "new_description": "x",
        })


@pytest.mark.asyncio
async def test_edit_character_replaces_description_text() -> None:
    from app.agent_runtime.tools.impls.context.character import EditCharacterTool

    tool = EditCharacterTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    character = SimpleNamespace(
        id="char-1",
        project_id="proj-1",
        name="Linu",
        description="Tokoh Utama",
        is_favorited=False,
    )
    updated_character = SimpleNamespace(
        id="char-1",
        project_id="proj-1",
        name="Linu",
        description="Tokoh Utama dan kawan lama",
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
        mock_character_repo.list_all_by_project = AsyncMock(return_value=[character])
        mock_character_service.update_character = AsyncMock(return_value=updated_character)
        mock_record_diffs.return_value = ["char-1"]

        result = await tool.ainvoke(
            {
                "name": "Linu",
                "old_description": "Tokoh Utama",
                "new_description": "Tokoh Utama dan kawan lama",
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
            "text": "Tokoh Utama",
        },
        {
            "type": "added",
            "before_line_number": None,
            "after_line_number": 1,
            "text": "Tokoh Utama dan kawan lama",
        },
    ]


@pytest.mark.asyncio
async def test_edit_character_rejects_over_limit_replacement_without_updating() -> None:
    from app.agent_runtime.tools.impls.context.character import EditCharacterTool

    tool = EditCharacterTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    character = SimpleNamespace(
        id="char-1",
        project_id="proj-1",
        name="Linu",
        description="Isi lama",
        is_favorited=False,
    )

    with patch(
        "app.agent_runtime.tools.impls.context.character.create_session"
    ) as mock_cs, patch(
        "app.agent_runtime.tools.impls.context.character.character_repo"
    ) as mock_character_repo, patch(
        "app.agent_runtime.tools.impls.context.character.character_service"
    ) as mock_character_service:
        mock_cs.return_value = AsyncMock()
        mock_character_repo.list_all_by_project = AsyncMock(return_value=[character])
        mock_character_service.update_character = AsyncMock()

        result = await tool.ainvoke(
            {
                "name": "Linu",
                "old_description": "Isi lama",
                "new_description": "\n".join("Isi" for _ in range(2001)),
            }
        )

    assert "Konten melebihi batas" in json.loads(result)["message"]
    mock_character_service.update_character.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_character_removes_name() -> None:
    from app.agent_runtime.tools.impls.context.character import DeleteCharacterTool

    tool = DeleteCharacterTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    character = SimpleNamespace(
        id="char-1",
        project_id="proj-1",
        name="Linu",
        description="Tokoh Utama",
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
        mock_character_repo.list_all_by_project = AsyncMock(return_value=[character])
        mock_character_service.delete_character = AsyncMock(return_value=None)
        mock_record_diffs.return_value = ["char-1"]

        result = await tool.ainvoke({"name": "Linu"})

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["character_diff"]["operation"] == "delete"
    assert data["metadata"]["character_diff"]["character_id"] == "char-1"
    assert data["metadata"]["character_diff"]["character_name"] == "Linu"


@pytest.mark.asyncio
async def test_list_world_entries_returns_enabled_entry_titles() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import ListWorldEntriesTool

    tool = ListWorldEntriesTool(_state=_make_state())
    entries = [
        SimpleNamespace(id="e1", name="Tokoh Utama", uid=1, order=1, content="Linu"),
        SimpleNamespace(id="e2", name="Faksi", uid=2, order=2, content="Perkumpulan Kabut Biru"),
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
            {"title": "Tokoh Utama", "uid": 1, "order": 1},
            {"title": "Faksi", "uid": 2, "order": 2},
        ]
    }


@pytest.mark.asyncio
async def test_read_world_entry_reads_content_by_title() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import ReadWorldEntryTool

    tool = ReadWorldEntryTool(_state=_make_state())
    entries = [
        SimpleNamespace(id="e1", name="Tokoh Utama", uid=1, order=1, content="Linu\nkawan lama"),
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
        mock_entry_repo.list_all_by_world_info = AsyncMock(return_value=entries)

        result = await tool.ainvoke({"title": "Tokoh Utama"})

    assert json.loads(result) == {
        "title": "Tokoh Utama",
        "uid": 1,
        "order": 1,
        "content": "1|Linu\n2|kawan lama",
    }


@pytest.mark.asyncio
async def test_read_world_entry_rejects_duplicate_titles() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import ReadWorldEntryTool

    tool = ReadWorldEntryTool(_state=_make_state())
    entries = [
        SimpleNamespace(id="e1", name="Tokoh Utama", uid=1, order=1, content="Satu"),
        SimpleNamespace(id="e2", name="Tokoh Utama", uid=2, order=2, content="Dua"),
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
        mock_entry_repo.list_all_by_world_info = AsyncMock(return_value=entries)

        result = await tool.ainvoke({"title": "Tokoh Utama"})

    data = json.loads(result)
    assert data["type"] == "fail"
    assert data["message"] == "Judul entri buku dunia tidak unik: Tokoh Utama"


@pytest.mark.asyncio
async def test_create_world_entry_returns_diff() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import CreateWorldEntryTool

    tool = CreateWorldEntryTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    created = SimpleNamespace(
        id="e1",
        world_info_id="world-1",
        name="Tokoh Utama",
        uid=1,
        order=1,
        content="Linu",
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
        mock_entry_repo.list_all_by_world_info = AsyncMock(return_value=[])
        mock_entry_service.create_entry = AsyncMock(return_value=created)
        mock_record_diffs.return_value = ["e1"]

        result = await tool.ainvoke({"title": "Tokoh Utama", "content": "Linu"})

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["world_info_id"] == "world-1"
    assert data["metadata"]["world_entry_diff"] == {
        "operation": "create",
        "entry_id": "e1",
        "entry_title": "Tokoh Utama",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "Linu",
                    }
                ],
            }
        ],
    }


async def test_create_world_entry_serializes_parallel_creates_per_world() -> None:
    from app.agent_runtime.tools.impls import _locks
    from app.agent_runtime.tools.impls.context import world_entry as we

    _locks._LOCKS.clear()
    entered = asyncio.Event()
    release = asyncio.Event()
    call_count = 0

    async def list_entries(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            entered.set()
            await release.wait()
        return []

    created = SimpleNamespace(
        id="e1",
        world_info_id="world-1",
        uid=1,
        name="Tokoh Utama",
        order=1,
        content="Linu",
        token_count=2,
        is_enabled=True,
    )
    we_name = "app.agent_runtime.tools.impls.context.world_entry"
    with patch(f"{we_name}.create_session") as mock_cs, patch(
        f"{we_name}.world_info_repo"
    ) as mock_world_repo, patch(
        f"{we_name}.world_info_entry_repo"
    ) as mock_entry_repo, patch(
        f"{we_name}.world_info_entry_service"
    ) as mock_entry_service, patch(
        f"{we_name}.record_world_entry_diffs", AsyncMock(return_value=["e1"])
    ):
        mock_cs.return_value = AsyncMock()
        mock_world_repo.get_by_project_id = AsyncMock(return_value=SimpleNamespace(id="world-1"))
        mock_entry_repo.list_all_by_world_info = AsyncMock(side_effect=list_entries)
        mock_entry_service.create_entry = AsyncMock(return_value=created)

        def make_tool():
            return we.CreateWorldEntryTool(
                _state={**_make_state(), "current_revision_id": "rev-1"}
            )

        task1 = asyncio.create_task(
            make_tool().ainvoke({"title": "Tokoh Utama", "content": "Linu"})
        )
        await entered.wait()
        task2 = asyncio.create_task(
            make_tool().ainvoke({"title": "Tokoh Pendukung", "content": "Linu"})
        )
        await asyncio.sleep(0.05)
        assert not task2.done()
        release.set()
        await asyncio.gather(task1, task2)


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
        mock_entry_repo.list_all_by_world_info = AsyncMock(
            return_value=[SimpleNamespace(id="e1", name="Tokoh Utama", uid=1, order=1, content="")]
        )

        result = await tool.ainvoke({"title": "Tokoh Utama", "content": "Linu"})

    data = json.loads(result)
    assert data["type"] == "fail"
    assert data["message"] == "Judul entri buku dunia sudah ada: Tokoh Utama"


@pytest.mark.asyncio
async def test_create_world_entry_rejects_over_limit_content_without_creating() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import CreateWorldEntryTool

    tool = CreateWorldEntryTool(_state={**_make_state(), "current_revision_id": "rev-1"})

    with patch(
        "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_service"
    ) as mock_entry_service:
        mock_entry_service.create_entry = AsyncMock()

        result = await tool.ainvoke(
            {"title": "Tokoh Utama", "content": "\n".join("Isi" for _ in range(2001))}
        )

    assert "Konten melebihi batas" in json.loads(result)["message"]
    mock_entry_service.create_entry.assert_not_awaited()


def test_edit_world_entry_input_rejects_empty_old_content() -> None:
    from pydantic import ValidationError

    from app.agent_runtime.tools.impls.context.world_entry import EditWorldEntryInput

    with pytest.raises(ValidationError):
        EditWorldEntryInput.model_validate({
            "title": "Tokoh Utama",
            "old_content": "",
            "new_content": "x",
        })


@pytest.mark.asyncio
async def test_edit_world_entry_returns_diff() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import EditWorldEntryTool

    tool = EditWorldEntryTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    entry = SimpleNamespace(
        id="e1",
        world_info_id="world-1",
        name="Tokoh Utama",
        uid=1,
        order=1,
        content="Linu",
        token_count=2,
        is_enabled=True,
    )
    updated_entry = SimpleNamespace(
        id="e1",
        world_info_id="world-1",
        name="Tokoh Utama",
        uid=1,
        order=1,
        content="Linu dan kawan lama",
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
        mock_entry_repo.list_all_by_world_info = AsyncMock(return_value=[entry])
        mock_entry_service.update_entry = AsyncMock(return_value=updated_entry)
        mock_record_diffs.return_value = ["e1"]

        result = await tool.ainvoke(
            {"title": "Tokoh Utama", "old_content": "Linu", "new_content": "Linu dan kawan lama"}
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
                    "text": "Linu",
                },
                {
                    "type": "added",
                    "before_line_number": None,
                    "after_line_number": 1,
                    "text": "Linu dan kawan lama",
                },
            ],
        }
    ]


@pytest.mark.asyncio
async def test_edit_world_entry_rejects_over_limit_replacement_without_updating() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import EditWorldEntryTool

    tool = EditWorldEntryTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    entry = SimpleNamespace(
        id="e1",
        world_info_id="world-1",
        name="Tokoh Utama",
        uid=1,
        order=1,
        content="Isi lama",
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
    ) as mock_entry_service:
        mock_cs.return_value = AsyncMock()
        mock_world_repo.get_by_project_id = AsyncMock(return_value=SimpleNamespace(id="world-1"))
        mock_entry_repo.list_all_by_world_info = AsyncMock(return_value=[entry])
        mock_entry_service.update_entry = AsyncMock()

        result = await tool.ainvoke(
            {
                "title": "Tokoh Utama",
                "old_content": "Isi lama",
                "new_content": "\n".join("Isi" for _ in range(2001)),
            }
        )

    assert "Konten melebihi batas" in json.loads(result)["message"]
    mock_entry_service.update_entry.assert_not_awaited()


@pytest.mark.asyncio
async def test_edit_world_entry_rejects_duplicate_new_title() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import EditWorldEntryTool

    tool = EditWorldEntryTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    entries = [
        SimpleNamespace(id="e1", name="Tokoh Utama", uid=1, order=1, content="Linu"),
        SimpleNamespace(id="e2", name="Antagonis", uid=2, order=2, content="Semmi"),
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
        mock_entry_repo.list_all_by_world_info = AsyncMock(return_value=entries)

        result = await tool.ainvoke({"title": "Tokoh Utama", "new_title": "Antagonis"})

    data = json.loads(result)
    assert data["type"] == "fail"
    assert data["message"] == "Judul entri buku dunia sudah ada: Antagonis"


@pytest.mark.asyncio
async def test_delete_world_entry_removes_title() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import DeleteWorldEntryTool

    tool = DeleteWorldEntryTool(_state={**_make_state(), "current_revision_id": "rev-1"})
    entry = SimpleNamespace(
        id="e1",
        world_info_id="world-1",
        name="Tokoh Utama",
        uid=1,
        order=1,
        content="Linu",
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
        mock_entry_repo.list_all_by_world_info = AsyncMock(return_value=[entry])
        mock_entry_service.delete_entry = AsyncMock(return_value=None)
        mock_record_diffs.return_value = ["e1"]

        result = await tool.ainvoke({"title": "Tokoh Utama"})

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["world_info_id"] == "world-1"
    assert data["metadata"]["world_entry_diff"]["operation"] == "delete"
    assert data["metadata"]["world_entry_diff"]["entry_id"] == "e1"
    assert data["metadata"]["world_entry_diff"]["entry_title"] == "Tokoh Utama"
