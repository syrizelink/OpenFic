from unittest.mock import AsyncMock, MagicMock, patch


def _make_state() -> dict:
    return {
        "session_id": "sess-1",
        "task_id": "task-1",
        "project_id": "proj-1",
        "current_revision_id": "rev-1",
    }


def _make_world_info(world_info_id: str = "world-1") -> MagicMock:
    world_info = MagicMock()
    world_info.id = world_info_id
    return world_info


def _make_world_entry(
    *,
    entry_id: str = "entry-1",
    title: str = "Entri Lama",
    content: str = "Isi lama",
) -> MagicMock:
    entry = MagicMock()
    entry.id = entry_id
    entry.name = title
    entry.uid = 1
    entry.order = 1
    entry.content = content
    entry.token_count = 0
    entry.is_enabled = True
    return entry


def _make_character(
    *,
    character_id: str = "character-1",
    name: str = "Tokoh Lama",
    description: str = "Deskripsi lama",
) -> MagicMock:
    character = MagicMock()
    character.id = character_id
    character.name = name
    character.description = description
    return character


async def test_create_world_entry_builds_approval_diff_preview() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import CreateWorldEntryTool

    runtime_session = AsyncMock()
    tool = CreateWorldEntryTool(_state=_make_state())
    object.__setattr__(tool, "_config", {"configurable": {"db_session": runtime_session}})

    with (
        patch(
            "app.agent_runtime.tools.impls.context.world_entry.world_info_repo.get_by_project_id",
            AsyncMock(return_value=_make_world_info()),
        ),
        patch(
            "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo.list_all_by_world_info",
            AsyncMock(return_value=[]),
        ),
    ):
        preview = await tool.build_interrupt_preview({"title": "Entri Baru", "content": "Isi setelan"})

    assert preview is not None
    assert preview["type"] == "preview"
    assert preview["success"] is True
    assert preview["reason"] == "approval_preview"
    assert preview["metadata"]["world_entry_diff"] == {
        "operation": "create",
        "entry_title": "Entri Baru",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "Isi setelan",
                    }
                ],
            }
        ],
    }


async def test_edit_world_entry_builds_approval_diff_preview() -> None:
    from app.agent_runtime.tools.impls.context.world_entry import EditWorldEntryTool

    runtime_session = AsyncMock()
    entry = _make_world_entry()
    tool = EditWorldEntryTool(_state=_make_state())
    object.__setattr__(tool, "_config", {"configurable": {"db_session": runtime_session}})

    with (
        patch(
            "app.agent_runtime.tools.impls.context.world_entry.world_info_repo.get_by_project_id",
            AsyncMock(return_value=_make_world_info()),
        ),
        patch(
            "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo.list_all_by_world_info",
            AsyncMock(return_value=[entry]),
        ),
    ):
        preview = await tool.build_interrupt_preview(
            {"title": "Entri Lama", "old_content": "Isi lama", "new_content": "Isi baru"}
        )

    assert preview is not None
    assert preview["type"] == "preview"
    assert preview["success"] is True
    assert preview["reason"] == "approval_preview"
    assert preview["metadata"]["world_entry_diff"] == {
        "operation": "edit",
        "entry_id": "entry-1",
        "entry_title": "Entri Lama",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "removed",
                        "before_line_number": 1,
                        "after_line_number": None,
                        "text": "Isi lama",
                    },
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "Isi baru",
                    },
                ],
            }
        ],
    }


async def test_create_character_builds_approval_diff_preview() -> None:
    from app.agent_runtime.tools.impls.context.character import CreateCharacterTool

    runtime_session = AsyncMock()
    tool = CreateCharacterTool(_state=_make_state())
    object.__setattr__(tool, "_config", {"configurable": {"db_session": runtime_session}})

    with patch(
        "app.agent_runtime.tools.impls.context.character.character_repo.list_all_by_project",
        AsyncMock(return_value=[]),
    ):
        preview = await tool.build_interrupt_preview({"name": "Tokoh Baru", "description": "Deskripsi tokoh"})

    assert preview is not None
    assert preview["type"] == "preview"
    assert preview["success"] is True
    assert preview["reason"] == "approval_preview"
    assert preview["metadata"]["character_diff"] == {
        "operation": "create",
        "character_name": "Tokoh Baru",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "Deskripsi tokoh",
                    }
                ],
            }
        ],
    }


async def test_edit_character_builds_approval_diff_preview() -> None:
    from app.agent_runtime.tools.impls.context.character import EditCharacterTool

    runtime_session = AsyncMock()
    character = _make_character()
    tool = EditCharacterTool(_state=_make_state())
    object.__setattr__(tool, "_config", {"configurable": {"db_session": runtime_session}})

    with patch(
        "app.agent_runtime.tools.impls.context.character.character_repo.list_all_by_project",
        AsyncMock(return_value=[character]),
    ):
        preview = await tool.build_interrupt_preview(
            {"name": "Tokoh Lama", "old_description": "Deskripsi lama", "new_description": "Deskripsi baru"}
        )

    assert preview is not None
    assert preview["type"] == "preview"
    assert preview["success"] is True
    assert preview["reason"] == "approval_preview"
    assert preview["metadata"]["character_diff"] == {
        "operation": "edit",
        "character_id": "character-1",
        "character_name": "Tokoh Lama",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "removed",
                        "before_line_number": 1,
                        "after_line_number": None,
                        "text": "Deskripsi lama",
                    },
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "Deskripsi baru",
                    },
                ],
            }
        ],
    }
