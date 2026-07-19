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
    title: str = "旧条目",
    content: str = "旧内容",
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
    name: str = "旧角色",
    description: str = "旧描述",
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
            "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo.list_by_world_info",
            AsyncMock(return_value=[]),
        ),
    ):
        preview = await tool.build_interrupt_preview({"title": "新条目", "content": "设定内容"})

    assert preview is not None
    assert preview["type"] == "preview"
    assert preview["success"] is True
    assert preview["reason"] == "approval_preview"
    assert preview["metadata"]["world_entry_diff"] == {
        "operation": "create",
        "entry_title": "新条目",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "设定内容",
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
            "app.agent_runtime.tools.impls.context.world_entry.world_info_entry_repo.list_by_world_info",
            AsyncMock(return_value=[entry]),
        ),
    ):
        preview = await tool.build_interrupt_preview(
            {"title": "旧条目", "old_content": "旧内容", "new_content": "新内容"}
        )

    assert preview is not None
    assert preview["type"] == "preview"
    assert preview["success"] is True
    assert preview["reason"] == "approval_preview"
    assert preview["metadata"]["world_entry_diff"] == {
        "operation": "edit",
        "entry_id": "entry-1",
        "entry_title": "旧条目",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "removed",
                        "before_line_number": 1,
                        "after_line_number": None,
                        "text": "旧内容",
                    },
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "新内容",
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
        "app.agent_runtime.tools.impls.context.character.character_repo.list_by_project",
        AsyncMock(return_value=([], 0)),
    ):
        preview = await tool.build_interrupt_preview({"name": "新角色", "description": "角色描述"})

    assert preview is not None
    assert preview["type"] == "preview"
    assert preview["success"] is True
    assert preview["reason"] == "approval_preview"
    assert preview["metadata"]["character_diff"] == {
        "operation": "create",
        "character_name": "新角色",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "角色描述",
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
        "app.agent_runtime.tools.impls.context.character.character_repo.list_by_project",
        AsyncMock(return_value=([character], 1)),
    ):
        preview = await tool.build_interrupt_preview(
            {"name": "旧角色", "old_description": "旧描述", "new_description": "新描述"}
        )

    assert preview is not None
    assert preview["type"] == "preview"
    assert preview["success"] is True
    assert preview["reason"] == "approval_preview"
    assert preview["metadata"]["character_diff"] == {
        "operation": "edit",
        "character_id": "character-1",
        "character_name": "旧角色",
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "removed",
                        "before_line_number": 1,
                        "after_line_number": None,
                        "text": "旧描述",
                    },
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "新描述",
                    },
                ],
            }
        ],
    }
