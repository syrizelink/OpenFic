"""Tests for Agent note tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch


def _make_state() -> dict:
    return {
        "session_id": "sess-1",
        "task_id": "task-1",
        "project_id": "proj-1",
        "model_config": {},
        "active_agent": None,
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "message_checkpoints": [],
        "user_request": "",
        "current_revision_id": "rev-1",
    }


def _make_note(
    *,
    note_id: str = "note-1",
    title: str = "测试笔记",
    content: str = "测试内容",
    is_locked: bool = False,
    is_hidden: bool = False,
    project_id: str = "proj-1",
    category_id: str | None = None,
):
    note = MagicMock()
    note.id = note_id
    note.project_id = project_id
    note.category_id = category_id
    note.title = title
    note.content = content
    note.is_locked = is_locked
    note.is_hidden = is_hidden
    note.created_at = None
    note.updated_at = None
    return note


def _make_category(
    *,
    category_id: str = "cat-1",
    title: str = "分类A",
    parent_id: str | None = None,
    project_id: str = "proj-1",
):
    cat = MagicMock()
    cat.id = category_id
    cat.project_id = project_id
    cat.parent_id = parent_id
    cat.title = title
    return cat


async def test_read_note_rejects_hidden_note() -> None:
    from app.agent_runtime.tools.impls.note.read_note import ReadNoteTool

    note = _make_note(note_id="note-1", title="隐藏", is_hidden=True)
    tool = ReadNoteTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.read_note.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.note.read_note.note_repo.get_by_id",
            AsyncMock(return_value=note),
        ):
            result = await tool.ainvoke({"note_ref": {"id": "note-1"}})
            mock_session.close.assert_called_once()

    data = json.loads(result)
    assert "error" in data
    assert "已隐藏" in data["error"]


async def test_edit_note_rejects_locked_note() -> None:
    from app.agent_runtime.tools.impls.note.edit_note import EditNoteTool

    note = _make_note(
        note_id="note-1", title="锁定笔记", is_locked=True, content="旧内容"
    )
    tool = EditNoteTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.edit_note.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.note.edit_note.note_repo.get_by_id",
            AsyncMock(return_value=note),
        ):
            result = await tool.ainvoke(
                {
                    "note_ref": {"id": "note-1"},
                    "old_content": "旧内容",
                    "new_content": "新内容",
                }
            )
            mock_session.close.assert_called_once()

    data = json.loads(result)
    assert "error" in data
    assert "已锁定" in data["error"]


async def test_edit_note_returns_success_and_diff_metadata() -> None:
    from app.agent_runtime.tools.impls.note.edit_note import EditNoteTool

    note = _make_note(note_id="note-1", title="测试笔记", content="旧内容")
    tool = EditNoteTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.edit_note.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with (
            patch(
                "app.agent_runtime.tools.impls.note.edit_note.note_repo.get_by_id",
                AsyncMock(return_value=note),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.edit_note.note_repo.list_by_project",
                AsyncMock(side_effect=[[note], [note]]),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.edit_note.note_repo.update_note",
                AsyncMock(),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.edit_note.record_note_diffs",
                AsyncMock(return_value=["note-1"]),
            ),
            patch(
                "app.background.jobs.service.commit_and_notify",
                AsyncMock(),
            ),
        ):
            result = await tool.ainvoke(
                {
                    "note_ref": {"id": "note-1"},
                    "old_content": "旧内容",
                    "new_content": "新内容",
                }
            )

    assert json.loads(result) == {
        "success": True,
        "metadata": {
            "note_diff": {
                "operation": "update",
                "note_id": "note-1",
                "note_title": "测试笔记",
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
        },
    }


async def test_delete_note_rejects_hidden_note() -> None:
    from app.agent_runtime.tools.impls.note.delete_note import DeleteNoteTool

    note = _make_note(note_id="note-1", title="隐藏笔记", is_hidden=True)
    tool = DeleteNoteTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.delete_note.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.note.delete_note.note_repo.get_by_id",
            AsyncMock(return_value=note),
        ):
            result = await tool.ainvoke({"note_ref": {"id": "note-1"}})
            mock_session.close.assert_called_once()

    data = json.loads(result)
    assert "error" in data
    assert "已隐藏" in data["error"]


async def test_delete_note_rejects_locked_note() -> None:
    from app.agent_runtime.tools.impls.note.delete_note import DeleteNoteTool

    note = _make_note(note_id="note-1", title="锁定笔记", is_locked=True)
    tool = DeleteNoteTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.delete_note.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.note.delete_note.note_repo.get_by_id",
            AsyncMock(return_value=note),
        ):
            result = await tool.ainvoke({"note_ref": {"id": "note-1"}})
            mock_session.close.assert_called_once()

    data = json.loads(result)
    assert "error" in data
    assert "已锁定" in data["error"]


async def test_delete_note_returns_success_and_diff_metadata() -> None:
    from app.agent_runtime.tools.impls.note.delete_note import DeleteNoteTool

    note = _make_note(note_id="note-1", title="测试笔记", content="测试内容")
    tool = DeleteNoteTool(_state=_make_state())

    with patch("app.agent_runtime.tools.impls.note.delete_note.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with (
            patch(
                "app.agent_runtime.tools.impls.note.delete_note.note_repo.get_by_id",
                AsyncMock(return_value=note),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.delete_note.note_repo.list_by_project",
                AsyncMock(side_effect=[[note], []]),
            ),
            patch("app.agent_runtime.tools.impls.note.delete_note.note_repo.delete", AsyncMock()),
            patch(
                "app.agent_runtime.tools.impls.note.delete_note.record_note_diffs",
                AsyncMock(return_value=["note-1"]),
            ),
            patch("app.background.jobs.service.commit_and_notify", AsyncMock()),
        ):
            result = await tool.ainvoke({"note_ref": {"id": "note-1"}})

    assert json.loads(result) == {
        "success": True,
        "metadata": {
            "note_diff": {
                "operation": "delete",
                "note_id": "note-1",
                "note_title": "测试笔记",
            }
        },
    }


async def test_list_notes_returns_only_visible_notes() -> None:
    from app.agent_runtime.tools.impls.note.list_notes import ListNotesTool

    cat1 = _make_category(category_id="cat-1", title="设定")
    visible_note = _make_note(note_id="n-1", title="可见笔记")

    tool = ListNotesTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.list_notes.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with (
            patch(
                "app.agent_runtime.tools.impls.note.list_notes.note_category_repo.list_by_project",
                AsyncMock(return_value=[cat1]),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.list_notes.note_repo.list_by_project",
                AsyncMock(return_value=[visible_note]),
            ),
        ):
            result = await tool.ainvoke({"path": "/"})
            mock_session.close.assert_called_once()

    data = json.loads(result)
    assert data["path"] == "/"
    note_items = [i for i in data["items"] if i["type"] == "note"]
    assert all(i["id"] != "n-hidden" for i in note_items)


async def test_read_note_returns_content_without_line_numbers() -> None:
    from app.agent_runtime.tools.impls.note.read_note import ReadNoteTool

    note = _make_note(content="第一段\n第二段")
    tool = ReadNoteTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.read_note.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.note.read_note.note_repo.get_by_id",
            AsyncMock(return_value=note),
        ):
            result = await tool.ainvoke({"note_ref": {"id": "note-1"}})
            mock_session.close.assert_called_once()

    data = json.loads(result)
    assert data["content"] == "第一段\n第二段"
    assert "1|" not in data["content"]


async def test_write_note_creates_note_and_returns_success() -> None:
    from app.agent_runtime.tools.impls.note.write_note import WriteNoteTool

    tool = WriteNoteTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.write_note.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session

        async def _fake_create(session, note):
            note.id = "note-new"
            return note

        with (
            patch(
                "app.agent_runtime.tools.impls.note.write_note.note_repo.list_by_project",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.write_note.note_repo.create",
                AsyncMock(side_effect=_fake_create),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.write_note.record_note_diffs",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.background.jobs.service.commit_and_notify",
                AsyncMock(),
            ),
        ):
            result = await tool.ainvoke({"title": "新笔记", "content": "正文内容"})
            mock_session.close.assert_called_once()

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["note_diff"]["operation"] == "create"
    assert data["metadata"]["note_diff"]["note_id"] == "note-new"
    assert data["metadata"]["note_diff"]["note_title"] == "新笔记"
    assert data["metadata"]["note_diff"]["category_id"] is None
    assert data["metadata"]["note_diff"]["sections"][0]["type"] == "content"


async def test_write_note_builds_approval_diff_preview() -> None:
    from app.agent_runtime.tools.impls.note.write_note import WriteNoteTool

    runtime_session = AsyncMock()
    tool = WriteNoteTool(_state=_make_state())
    object.__setattr__(tool, "_config", {"configurable": {"db_session": runtime_session}})

    with patch(
        "app.agent_runtime.tools.impls.note.write_note.note_repo.list_by_project",
        AsyncMock(return_value=[]),
    ):
        preview = await tool.build_interrupt_preview(
            {"title": "新笔记", "content": "第一行\n第二行"}
        )

    assert preview is not None
    assert preview["type"] == "preview"
    assert preview["success"] is True
    assert preview["reason"] == "approval_preview"
    assert preview["metadata"]["note_diff"] == {
        "operation": "create",
        "note_title": "新笔记",
        "category_id": None,
        "sections": [
            {
                "type": "content",
                "lines": [
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 1,
                        "text": "第一行",
                    },
                    {
                        "type": "added",
                        "before_line_number": None,
                        "after_line_number": 2,
                        "text": "第二行",
                    },
                ],
            }
        ],
    }


async def test_edit_note_builds_approval_diff_preview() -> None:
    from app.agent_runtime.tools.impls.note.edit_note import EditNoteTool

    runtime_session = AsyncMock()
    note = _make_note(note_id="note-1", title="测试笔记", content="旧内容")
    tool = EditNoteTool(_state=_make_state())
    object.__setattr__(tool, "_config", {"configurable": {"db_session": runtime_session}})

    with patch(
        "app.agent_runtime.tools.impls.note.edit_note.note_repo.get_by_id",
        AsyncMock(return_value=note),
    ):
        preview = await tool.build_interrupt_preview(
            {
                "note_ref": {"id": "note-1"},
                "old_content": "旧内容",
                "new_content": "新内容",
            }
        )

    assert preview is not None
    assert preview["type"] == "preview"
    assert preview["success"] is True
    assert preview["reason"] == "approval_preview"
    assert preview["metadata"]["note_diff"] == {
        "operation": "update",
        "note_id": "note-1",
        "note_title": "测试笔记",
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


async def test_move_note_rejects_locked_note() -> None:
    from app.agent_runtime.tools.impls.note.move_note import MoveNoteTool

    note = _make_note(note_id="note-1", title="锁定笔记", is_locked=True)
    tool = MoveNoteTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.move_note.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.note.move_note.note_repo.get_by_id",
            AsyncMock(return_value=note),
        ):
            result = await tool.ainvoke(
                {"note_ref": {"id": "note-1"}, "target_category_ref": None}
            )
            mock_session.close.assert_called_once()

    data = json.loads(result)
    assert "error" in data
    assert "已锁定" in data["error"]


async def test_move_note_returns_success_and_metadata() -> None:
    from app.agent_runtime.tools.impls.note.move_note import MoveNoteTool

    note = _make_note(note_id="note-1", title="测试笔记", category_id="cat-1")
    category = _make_category(category_id="cat-2", title="目标分类")
    moved = _make_note(note_id="note-1", title="测试笔记", category_id="cat-2")
    tool = MoveNoteTool(_state=_make_state())

    with patch("app.agent_runtime.tools.impls.note.move_note.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with (
            patch(
                "app.agent_runtime.tools.impls.note.move_note.note_repo.get_by_id",
                AsyncMock(return_value=note),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.move_note.note_category_repo.get_by_id",
                AsyncMock(return_value=category),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.move_note.note_repo.list_by_project",
                AsyncMock(side_effect=[[note], [moved]]),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.move_note.note_service.move_item",
                AsyncMock(return_value=moved),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.move_note.record_note_diffs",
                AsyncMock(return_value=["note-1"]),
            ),
            patch("app.background.jobs.service.commit_and_notify", AsyncMock()),
        ):
            result = await tool.ainvoke(
                {"note_ref": {"id": "note-1"}, "target_category_ref": {"id": "cat-2"}}
            )

    assert json.loads(result) == {
        "success": True,
        "metadata": {
            "note_diff": {
                "operation": "move",
                "note_id": "note-1",
                "note_title": "测试笔记",
                "category_id": "cat-2",
                "target_category_id": "cat-2",
                "target_category_title": "目标分类",
            }
        },
    }


async def test_create_note_category_returns_success_and_metadata() -> None:
    from app.agent_runtime.tools.impls.note.create_note_category import CreateNoteCategoryTool

    created = _make_category(category_id="cat-new", title="新分类", parent_id="cat-1")
    tool = CreateNoteCategoryTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.create_note_category.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with (
            patch(
                "app.agent_runtime.tools.impls.note.create_note_category.note_category_repo.get_by_id",
                AsyncMock(return_value=_make_category()),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.create_note_category.note_category_repo.list_by_project",
                AsyncMock(side_effect=[[_make_category()], [_make_category(), created]]),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.create_note_category.note_category_repo.create",
                AsyncMock(return_value=created),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.create_note_category.record_note_category_diffs",
                AsyncMock(return_value=["cat-new"]),
            ),
            patch("app.background.jobs.service.commit_and_notify", AsyncMock()),
        ):
            result = await tool.ainvoke({"title": "新分类", "parent_ref": {"id": "cat-1"}})

    assert json.loads(result) == {
        "success": True,
        "metadata": {
            "category": {"id": "cat-new", "title": "新分类", "parent_id": "cat-1"}
        },
    }


async def test_create_note_category_builds_approval_preview() -> None:
    from app.agent_runtime.tools.impls.note.create_note_category import CreateNoteCategoryTool

    runtime_session = AsyncMock()
    tool = CreateNoteCategoryTool(_state=_make_state())
    object.__setattr__(tool, "_config", {"configurable": {"db_session": runtime_session}})

    with patch(
        "app.agent_runtime.tools.impls.note.create_note_category.note_category_repo.list_by_project",
        AsyncMock(return_value=[_make_category(category_id="cat-1", title="已有分类")]),
    ):
        preview = await tool.build_interrupt_preview({"title": "新分类"})

    assert preview == {
        "type": "preview",
        "success": True,
        "reason": "approval_preview",
        "metadata": {
            "category": {
                "title": "新分类",
                "parent_id": None,
            }
        },
    }


async def test_edit_note_category_returns_success_and_rename_metadata() -> None:
    from app.agent_runtime.tools.impls.note.edit_note_category import EditNoteCategoryTool

    category = _make_category(category_id="cat-1", title="旧分类")
    renamed_category = _make_category(category_id="cat-1", title="新分类")
    tool = EditNoteCategoryTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.edit_note_category.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with (
            patch(
                "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.get_by_id",
                AsyncMock(return_value=category),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.list_by_project",
                AsyncMock(side_effect=[[category], [renamed_category]]),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.update_category",
                AsyncMock(return_value=renamed_category),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.edit_note_category.record_note_category_diffs",
                AsyncMock(return_value=["cat-1"]),
            ),
            patch("app.background.jobs.service.commit_and_notify", AsyncMock()),
        ):
            result = await tool.ainvoke(
                {"category_ref": {"id": "cat-1"}, "new_title": "新分类"}
            )

    assert json.loads(result) == {
        "success": True,
        "metadata": {
            "category": {
                "id": "cat-1",
                "title": "新分类",
                "previous_title": "旧分类",
                "parent_id": None,
            }
        },
    }


async def test_edit_note_category_builds_approval_preview() -> None:
    from app.agent_runtime.tools.impls.note.edit_note_category import EditNoteCategoryTool

    runtime_session = AsyncMock()
    tool = EditNoteCategoryTool(_state=_make_state())
    object.__setattr__(tool, "_config", {"configurable": {"db_session": runtime_session}})

    with patch(
        "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.get_by_id",
        AsyncMock(return_value=_make_category(category_id="cat-1", title="旧分类")),
    ), patch(
        "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.list_by_project",
        AsyncMock(return_value=[_make_category(category_id="cat-1", title="旧分类")]),
    ):
        preview = await tool.build_interrupt_preview(
            {"category_ref": {"id": "cat-1"}, "new_title": "新分类"}
        )

    assert preview == {
        "type": "preview",
        "success": True,
        "reason": "approval_preview",
        "metadata": {
            "category": {
                "id": "cat-1",
                "title": "新分类",
                "previous_title": "旧分类",
                "parent_id": None,
            }
        },
    }


async def test_edit_note_category_rejects_duplicate_sibling_title() -> None:
    from app.agent_runtime.tools.impls.note.edit_note_category import EditNoteCategoryTool

    category = _make_category(category_id="cat-1", title="旧分类")
    existing_sibling = _make_category(category_id="cat-2", title="新分类")
    tool = EditNoteCategoryTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.edit_note_category.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with (
            patch(
                "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.get_by_id",
                AsyncMock(return_value=category),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.list_by_project",
                AsyncMock(return_value=[category, existing_sibling]),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.update_category",
                AsyncMock(),
            ) as update_category,
            patch(
                "app.agent_runtime.tools.impls.note.edit_note_category.record_note_category_diffs",
                AsyncMock(return_value=["cat-1"]),
            ),
            patch("app.background.jobs.service.commit_and_notify", AsyncMock()),
        ):
            result = await tool.ainvoke(
                {"category_ref": {"id": "cat-1"}, "new_title": "新分类"}
            )

    assert json.loads(result)["error"] == "同级分类已存在同名标题: 新分类"
    update_category.assert_not_awaited()


async def test_edit_note_category_rejects_category_from_another_project() -> None:
    from app.agent_runtime.tools.impls.note.edit_note_category import EditNoteCategoryTool

    tool = EditNoteCategoryTool(_state=_make_state())
    category = _make_category(project_id="proj-other")

    with patch(
        "app.agent_runtime.tools.impls.note.edit_note_category.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.note.edit_note_category.note_category_repo.get_by_id",
            AsyncMock(return_value=category),
        ):
            result = await tool.ainvoke(
                {"category_ref": {"id": "cat-1"}, "new_title": "新分类"}
            )

    assert json.loads(result)["error"] == "分类不属于当前项目"


async def test_delete_note_category_cascades_and_records_revisions() -> None:
    from app.agent_runtime.tools.impls.note.delete_note_category import (
        DeleteNoteCategoryTool,
    )

    category = _make_category(category_id="cat-1", title="待删除")
    note = _make_note(note_id="note-1", title="分类内笔记", category_id="cat-1")
    tool = DeleteNoteCategoryTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.note.delete_note_category.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with (
            patch(
                "app.agent_runtime.tools.impls.note.delete_note_category.note_category_repo.get_by_id",
                AsyncMock(return_value=category),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.delete_note_category.note_category_repo.list_by_project",
                AsyncMock(side_effect=[[category], []]),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.delete_note_category.note_repo.list_by_project",
                AsyncMock(side_effect=[[note], []]),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.delete_note_category.note_service.delete_category",
                AsyncMock(),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.delete_note_category.record_note_category_diffs",
                AsyncMock(return_value=["cat-1"]),
            ),
            patch(
                "app.agent_runtime.tools.impls.note.delete_note_category.record_note_diffs",
                AsyncMock(return_value=["note-1"]),
            ),
            patch("app.background.jobs.service.commit_and_notify", AsyncMock()),
        ):
            result = await tool.ainvoke({"category_ref": {"id": "cat-1"}})

    assert json.loads(result) == {
        "success": True,
        "metadata": {
            "category": {
                "id": "cat-1",
                "title": "待删除",
            }
        },
    }


async def test_delete_note_category_builds_cascade_approval_preview() -> None:
    from app.agent_runtime.tools.impls.note.delete_note_category import (
        DeleteNoteCategoryTool,
    )

    runtime_session = AsyncMock()
    tool = DeleteNoteCategoryTool(_state=_make_state())
    object.__setattr__(tool, "_config", {"configurable": {"db_session": runtime_session}})

    with (
        patch(
            "app.agent_runtime.tools.impls.note.delete_note_category.note_category_repo.get_by_id",
            AsyncMock(return_value=_make_category(category_id="cat-1", title="待删除")),
        ),
        patch(
            "app.agent_runtime.tools.impls.note.delete_note_category.note_category_repo.list_by_project",
            AsyncMock(
                return_value=[
                    _make_category(category_id="cat-1", title="待删除"),
                    _make_category(category_id="cat-2", title="子分类", parent_id="cat-1"),
                ]
            ),
        ),
        patch(
            "app.agent_runtime.tools.impls.note.delete_note_category.note_repo.list_by_project",
            AsyncMock(
                return_value=[
                    _make_note(note_id="note-1", title="分类内笔记", category_id="cat-1"),
                    _make_note(note_id="note-2", title="子分类笔记", category_id="cat-2"),
                ]
            ),
        ),
    ):
        preview = await tool.build_interrupt_preview({"category_ref": {"id": "cat-1"}})

    assert preview == {
        "type": "preview",
        "success": True,
        "reason": "approval_preview",
        "metadata": {
            "category": {
                "id": "cat-1",
                "title": "待删除",
            },
            "affected_category_count": 2,
            "affected_note_count": 2,
        },
    }


async def test_delete_note_category_rejects_category_from_another_project() -> None:
    from app.agent_runtime.tools.impls.note.delete_note_category import (
        DeleteNoteCategoryTool,
    )

    tool = DeleteNoteCategoryTool(_state=_make_state())
    category = _make_category(project_id="proj-other")

    with patch(
        "app.agent_runtime.tools.impls.note.delete_note_category.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.note.delete_note_category.note_category_repo.get_by_id",
            AsyncMock(return_value=category),
        ):
            result = await tool.ainvoke({"category_ref": {"id": "cat-1"}})

    assert json.loads(result)["error"] == "分类不属于当前项目"
