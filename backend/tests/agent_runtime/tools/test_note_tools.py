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
    assert data["type"] == "ok"
    assert data["success"] is True
    assert data["tool_name"] == "write_note"
    assert data["note"]["title"] == "新笔记"
    assert data["revision_id"] == "rev-1"
    assert data["note_diff"]["operation"] == "create"
    assert data["note_diff"]["sections"][0]["type"] == "content"


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
