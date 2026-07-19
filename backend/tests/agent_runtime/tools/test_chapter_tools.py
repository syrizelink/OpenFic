"""Tests for Agent chapter and volume tools."""

import json
from types import SimpleNamespace
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


def _make_volume(
    *,
    volume_id: str = "vol-1",
    order: int = 1,
    title: str = "第一卷",
    description: str | None = None,
    chapter_count: int = 2,
):
    volume = MagicMock()
    volume.id = volume_id
    volume.project_id = "proj-1"
    volume.order = order
    volume.title = title
    volume.description = description
    volume.chapter_count = chapter_count
    return volume


def _make_chapter(
    *,
    order: int = 1,
    title: str = "第一章",
    content: str = "内容测试",
    word_count: int = 4,
    chapter_id: str = "chap-1",
    volume_id: str = "vol-1",
):
    chapter = MagicMock()
    chapter.id = chapter_id
    chapter.order = order
    chapter.title = title
    chapter.content = content
    chapter.word_count = word_count
    chapter.project_id = "proj-1"
    chapter.volume_id = volume_id
    chapter.created_at = None
    chapter.updated_at = None
    return chapter


def _assert_success_payload(result: str, tool_name: str) -> dict:
    data = json.loads(result)
    assert data["type"] == "ok"
    assert data["success"] is True
    assert data["tool_name"] == tool_name
    assert data["revision_id"] == "rev-1"
    return data


async def test_list_volumes_returns_project_volumes() -> None:
    from app.agent_runtime.tools.impls.chapter.list_volumes import ListVolumesTool

    volumes = [
        _make_volume(order=1, title="第一卷", description="开端", chapter_count=2),
        _make_volume(volume_id="vol-2", order=2, title="第二卷", chapter_count=0),
    ]
    tool = ListVolumesTool(_state=_make_state())

    with patch("app.agent_runtime.tools.impls.chapter.list_volumes.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.list_volumes.volume_repo.list_by_project",
            AsyncMock(return_value=volumes),
        ) as list_by_project:
            result = await tool.ainvoke({})

    assert json.loads(result) == [
        {"order": 1, "title": "第一卷", "description": "开端", "chapter_count": 2},
        {"order": 2, "title": "第二卷", "description": None, "chapter_count": 0},
    ]
    list_by_project.assert_awaited_once_with(mock_session, "proj-1")
    mock_session.close.assert_called_once()


async def test_list_chapters_uses_required_volume_ref_and_volume_pagination() -> None:
    from app.agent_runtime.tools.impls.chapter.list_chapters import ListChaptersTool

    volume = _make_volume()
    chapters = [
        _make_chapter(order=1, title="第一章"),
        _make_chapter(order=2, title="第二章"),
    ]
    tool = ListChaptersTool(_state=_make_state())

    with patch("app.agent_runtime.tools.impls.chapter.list_chapters.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.list_chapters.volume_repo.list_by_project",
            AsyncMock(return_value=[volume]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.list_chapters.chapter_repo.list_by_volume",
            AsyncMock(return_value=chapters),
        ) as list_by_volume:
            result = await tool.ainvoke(
                {
                    "volume_ref": {"type": "order", "value": 1},
                    "offset": 5,
                    "limit": 10,
                }
            )

    assert json.loads(result) == [
        {"order": 1, "title": "第一章", "word_count": 4},
        {"order": 2, "title": "第二章", "word_count": 4},
    ]
    list_by_volume.assert_awaited_once_with(mock_session, "vol-1", offset=5, limit=10)


async def test_read_chapter_resolves_chapter_inside_volume() -> None:
    from app.agent_runtime.tools.impls.chapter.read_chapter import ReadChapterTool

    volume = _make_volume()
    chapter = _make_chapter(order=2, title="第二章", content="第一行\n第二行", word_count=6)
    tool = ReadChapterTool(_state=_make_state())

    with patch("app.agent_runtime.tools.impls.chapter.read_chapter.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.read_chapter.volume_repo.list_by_project",
            AsyncMock(return_value=[volume]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.read_chapter.chapter_repo.list_by_volume",
            AsyncMock(return_value=[chapter]),
        ) as list_by_volume:
            result = await tool.ainvoke(
                {
                    "volume_ref": {"type": "title", "value": "第一卷"},
                    "chapter_ref": {"type": "order", "value": 2},
                }
            )

    data = json.loads(result)
    assert data == {
        "order": 2,
        "title": "第二章",
        "content": "1|第一行\n2|第二行",
        "word_count": 6,
    }
    list_by_volume.assert_awaited_once_with(mock_session, "vol-1")


async def test_write_chapter_appends_to_volume_and_returns_volume_id() -> None:
    from app.agent_runtime.tools.impls.chapter.write_chapter import WriteChapterTool

    volume = _make_volume(chapter_count=3)
    created = _make_chapter(
        order=4,
        title="新章节",
        content="新内容",
        word_count=3,
        chapter_id="chap-new",
    )
    tool = WriteChapterTool(_state=_make_state())

    async def create_chapter(_session, chapter):
        chapter.id = created.id
        return chapter

    with patch("app.agent_runtime.tools.impls.chapter.write_chapter.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.volume_repo.list_by_project",
            AsyncMock(return_value=[volume]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.chapter_repo"
        ) as mock_repo, patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.record_chapter_diffs",
            AsyncMock(return_value=["chap-new"]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.record_agent_activity_for_change",
            AsyncMock(),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.refresh_volume_chapter_count",
            AsyncMock(),
        ) as refresh_volume_count, patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.refresh_project_stats",
            AsyncMock(),
        ), patch(
            "app.retrieval.chapter_index.safe_maybe_enqueue_auto_index", AsyncMock()
        ), patch(
            "app.retrieval.index_status.schedule_emit_index_status", lambda *_a, **_k: None
        ), patch(
            "app.background.jobs.service.commit_and_notify", AsyncMock()
        ):
            mock_repo.list_by_project = AsyncMock(side_effect=[[], [created]])
            mock_repo.get_max_order = AsyncMock(return_value=3)
            mock_repo.create = AsyncMock(side_effect=create_chapter)
            result = await tool.ainvoke(
                {
                    "volume_ref": {"type": "order", "value": 1},
                    "title": "新章节",
                    "content": "新内容",
                }
            )

    data = json.loads(result)
    assert set(data) == {"success", "word_count", "metadata"}
    assert data["success"] is True
    assert data["word_count"] == 3
    assert data["metadata"]["chapter_diff"]["operation"] == "create"
    assert data["metadata"]["chapter_diff"]["chapter_id"] == "chap-new"
    assert [section["type"] for section in data["metadata"]["chapter_diff"]["sections"]] == ["title", "content"]
    mock_repo.get_max_order.assert_awaited_once_with(mock_session, "vol-1")
    created_chapter = mock_repo.create.call_args[0][1]
    assert created_chapter.id == "chap-new"
    assert created_chapter.volume_id == "vol-1"
    assert created_chapter.order == 4
    refresh_volume_count.assert_awaited_once_with(mock_session, "vol-1")


async def test_write_chapter_insert_order_shifts_within_volume() -> None:
    from app.agent_runtime.tools.impls.chapter.write_chapter import WriteChapterTool

    volume = _make_volume()
    created = _make_chapter(order=2, title="插入章节", chapter_id="chap-new")
    tool = WriteChapterTool(_state=_make_state())

    async def create_chapter(_session, chapter):
        chapter.id = created.id
        return chapter

    with patch("app.agent_runtime.tools.impls.chapter.write_chapter.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.volume_repo.list_by_project",
            AsyncMock(return_value=[volume]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.chapter_repo"
        ) as mock_repo, patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.record_chapter_diffs",
            AsyncMock(return_value=["chap-new"]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.record_agent_activity_for_change",
            AsyncMock(),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.refresh_volume_chapter_count",
            AsyncMock(),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.write_chapter.refresh_project_stats",
            AsyncMock(),
        ), patch(
            "app.retrieval.chapter_index.safe_maybe_enqueue_auto_index", AsyncMock()
        ), patch(
            "app.retrieval.index_status.schedule_emit_index_status", lambda *_a, **_k: None
        ), patch(
            "app.background.jobs.service.commit_and_notify", AsyncMock()
        ):
            mock_repo.list_by_project = AsyncMock(side_effect=[[], [created]])
            mock_repo.list_by_volume = AsyncMock(return_value=[_make_chapter(order=2)])
            mock_repo.get_max_order = AsyncMock(return_value=5)
            mock_repo.shift_orders = AsyncMock()
            mock_repo.create = AsyncMock(side_effect=create_chapter)
            result = await tool.ainvoke(
                {
                    "volume_ref": {"type": "order", "value": 1},
                    "title": "插入章节",
                    "content": "插入内容",
                    "chapter_ref": {"type": "order", "value": 2},
                }
            )

    data = json.loads(result)
    assert set(data) == {"success", "word_count", "metadata"}
    assert data["success"] is True
    assert data["word_count"] == 4
    assert data["metadata"]["chapter_diff"]["operation"] == "create"
    assert data["metadata"]["chapter_diff"]["order"] == 2
    assert [section["type"] for section in data["metadata"]["chapter_diff"]["sections"]] == ["title", "content"]
    mock_repo.shift_orders.assert_awaited_once_with(mock_session, "vol-1", 2, 5, 1)


async def test_edit_chapter_resolves_inside_volume() -> None:
    from app.agent_runtime.tools.impls.chapter.edit_chapter import EditChapterTool

    volume = _make_volume()
    chapter = _make_chapter(order=1, title="旧标题", content="内容")
    tool = EditChapterTool(_state=_make_state())

    with patch("app.agent_runtime.tools.impls.chapter.edit_chapter.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.volume_repo.list_by_project",
            AsyncMock(return_value=[volume]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.chapter_repo"
        ) as mock_repo, patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.record_chapter_diffs",
            AsyncMock(return_value=["chap-1"]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.record_agent_activity_for_change",
            AsyncMock(),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.edit_chapter.refresh_project_stats",
            AsyncMock(),
        ), patch(
            "app.retrieval.chapter_index.safe_maybe_enqueue_auto_index", AsyncMock()
        ), patch(
            "app.retrieval.index_status.schedule_emit_index_status", lambda *_a, **_k: None
        ), patch(
            "app.background.jobs.service.commit_and_notify", AsyncMock()
        ):
            mock_repo.list_by_project = AsyncMock(return_value=[chapter])
            mock_repo.list_by_volume = AsyncMock(return_value=[chapter])
            mock_repo.update_chapter = AsyncMock()
            result = await tool.ainvoke(
                {
                    "volume_ref": {"type": "order", "value": 1},
                    "chapter_ref": {"type": "order", "value": 1},
                    "new_title": "新标题",
                }
            )

    data = json.loads(result)
    assert data == {
        "success": True,
        "word_count": 4,
        "metadata": {
            "chapter_diff": {
                "operation": "update",
                "chapter_id": "chap-1",
                "chapter_title": "新标题",
                "order": 1,
                "sections": [
                    {
                        "type": "title",
                        "lines": [
                            {
                                "type": "removed",
                                "before_line_number": 1,
                                "after_line_number": None,
                                "text": "旧标题",
                            },
                            {
                                "type": "added",
                                "before_line_number": None,
                                "after_line_number": 1,
                                "text": "新标题",
                            },
                        ],
                    }
                ],
            }
        },
    }
    mock_repo.list_by_volume.assert_awaited_once_with(mock_session, "vol-1")


async def test_delete_chapter_delegates_to_chapter_service() -> None:
    from app.agent_runtime.tools.impls.chapter.delete_chapter import DeleteChapterTool

    volume = _make_volume()
    chapter = _make_chapter(order=2)
    tool = DeleteChapterTool(_state=_make_state())

    with patch("app.agent_runtime.tools.impls.chapter.delete_chapter.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.delete_chapter.volume_repo.list_by_project",
            AsyncMock(return_value=[volume]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.delete_chapter.chapter_repo"
        ) as mock_repo, patch(
            "app.agent_runtime.tools.impls.chapter.delete_chapter.record_chapter_diffs",
            AsyncMock(return_value=["chap-1"]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.delete_chapter.record_agent_activity_for_change",
            AsyncMock(),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.delete_chapter.chapter_service",
            SimpleNamespace(delete_chapter=AsyncMock()),
            create=True,
        ) as mock_chapter_service:
            after_chapter = _make_chapter(order=1, chapter_id="chap-2")
            mock_repo.list_by_project = AsyncMock(side_effect=[[chapter, after_chapter], [after_chapter]])
            mock_repo.list_by_volume = AsyncMock(return_value=[chapter])
            mock_repo.delete = AsyncMock()
            mock_repo.get_max_order = AsyncMock(return_value=4)
            mock_repo.shift_orders = AsyncMock()
            result = await tool.ainvoke(
                {
                    "volume_ref": {"type": "order", "value": 1},
                    "chapter_ref": {"type": "order", "value": 2},
                }
            )

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["chapter_diff"] == {
        "operation": "delete",
        "chapter_id": "chap-1",
        "chapter_title": "第一章",
        "order": 2,
    }
    mock_chapter_service.delete_chapter.assert_awaited_once_with(
        mock_session,
        "chap-1",
        activity_source="agent",
        revision_id="rev-1",
        task_id="task-1",
        agent_session_id="sess-1",
    )
    mock_repo.delete.assert_not_called()
    mock_repo.shift_orders.assert_not_called()


async def test_create_volume_appends_to_project() -> None:
    from app.agent_runtime.tools.impls.chapter.create_volume import CreateVolumeTool

    created = _make_volume(volume_id="vol-new", order=3, title="第三卷", description="终局", chapter_count=0)
    tool = CreateVolumeTool(_state=_make_state())

    with patch("app.agent_runtime.tools.impls.chapter.create_volume.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.create_volume.volume_repo.get_max_order",
            AsyncMock(return_value=2),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.create_volume.volume_repo.create",
            AsyncMock(return_value=created),
        ) as create_volume:
            result = await tool.ainvoke({"title": "第三卷", "description": "终局"})

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["volume"] == {
        "order": 3,
        "title": "第三卷",
        "description": "终局",
        "chapter_count": 0,
    }
    volume_arg = create_volume.call_args[0][1]
    assert volume_arg.project_id == "proj-1"
    assert volume_arg.order == 3
    mock_session.commit.assert_called_once()


async def test_create_volume_builds_approval_preview() -> None:
    from app.agent_runtime.tools.impls.chapter.create_volume import CreateVolumeTool

    runtime_session = AsyncMock()
    tool = CreateVolumeTool(_state=_make_state())
    object.__setattr__(tool, "_config", {"configurable": {"db_session": runtime_session}})

    with patch(
        "app.agent_runtime.tools.impls.chapter.create_volume.volume_repo.get_max_order",
        AsyncMock(return_value=2),
    ):
        preview = await tool.build_interrupt_preview({"title": "第三卷", "description": "终局"})

    assert preview == {
        "type": "preview",
        "success": True,
        "reason": "approval_preview",
        "metadata": {
            "volume": {
                "order": 3,
                "title": "第三卷",
                "description": "终局",
                "chapter_count": 0,
            }
        },
    }


async def test_edit_volume_updates_title_and_description() -> None:
    from app.agent_runtime.tools.impls.chapter.edit_volume import EditVolumeTool

    volume = _make_volume(title="旧卷", description="旧描述")
    tool = EditVolumeTool(_state=_make_state())

    with patch("app.agent_runtime.tools.impls.chapter.edit_volume.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.edit_volume.volume_repo.list_by_project",
            AsyncMock(return_value=[volume]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.edit_volume.volume_repo.update_volume",
            AsyncMock(return_value=volume),
        ) as update_volume:
            result = await tool.ainvoke(
                {
                    "volume_ref": {"type": "title", "value": "旧卷"},
                    "new_title": "新卷",
                    "new_description": "新描述",
                }
            )

    assert json.loads(result) == {
        "success": True,
        "metadata": {
            "volume": {
                "order": 1,
                "title": "新卷",
                "description": "新描述",
                "chapter_count": 2,
            }
        },
    }
    update_volume.assert_awaited_once_with(mock_session, volume)


async def test_edit_volume_builds_approval_preview() -> None:
    from app.agent_runtime.tools.impls.chapter.edit_volume import EditVolumeTool

    runtime_session = AsyncMock()
    volume = _make_volume(title="旧卷", description="旧描述")
    tool = EditVolumeTool(_state=_make_state())
    object.__setattr__(tool, "_config", {"configurable": {"db_session": runtime_session}})

    with patch(
        "app.agent_runtime.tools.impls.chapter.edit_volume.volume_repo.list_by_project",
        AsyncMock(return_value=[volume]),
    ):
        preview = await tool.build_interrupt_preview(
            {
                "volume_ref": {"type": "title", "value": "旧卷"},
                "new_title": "新卷",
                "new_description": "新描述",
            }
        )

    assert preview == {
        "type": "preview",
        "success": True,
        "reason": "approval_preview",
        "metadata": {
            "volume": {
                "order": 1,
                "title": "新卷",
                "description": "新描述",
                "chapter_count": 2,
            }
        },
    }


async def test_delete_volume_requires_cascade_for_non_empty_volume() -> None:
    from app.agent_runtime.tools.impls.chapter.delete_volume import DeleteVolumeTool

    volume = _make_volume(chapter_count=1)
    tool = DeleteVolumeTool(_state=_make_state())

    with patch("app.agent_runtime.tools.impls.chapter.delete_volume.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.delete_volume.volume_repo.list_by_project",
            AsyncMock(return_value=[volume]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.delete_volume.chapter_repo.count_by_volume",
            AsyncMock(return_value=1),
        ):
            result = await tool.ainvoke(
                {"volume_ref": {"type": "order", "value": 1}, "cascade": False}
            )

    data = json.loads(result)
    assert "error" in data
    assert "cascade=true" in data["error"]
    mock_session.rollback.assert_called_once()


async def test_delete_volume_returns_success_only() -> None:
    from app.agent_runtime.tools.impls.chapter.delete_volume import DeleteVolumeTool

    volume = _make_volume(chapter_count=0)
    tool = DeleteVolumeTool(_state=_make_state())

    with patch("app.agent_runtime.tools.impls.chapter.delete_volume.create_session") as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.delete_volume.volume_repo.list_by_project",
            AsyncMock(return_value=[volume]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.delete_volume.chapter_repo.count_by_volume",
            AsyncMock(return_value=0),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.delete_volume.volume_service.delete_volume",
            AsyncMock(),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.delete_volume.refresh_project_stats",
            AsyncMock(),
        ):
            result = await tool.ainvoke({"volume_ref": {"type": "order", "value": 1}})

    assert json.loads(result) == {"success": True}


async def test_move_chapter_to_volume_appends_to_target_volume() -> None:
    from app.agent_runtime.tools.impls.chapter.move_chapter_to_volume import (
        MoveChapterToVolumeTool,
    )

    source = _make_volume(volume_id="vol-1", order=1, title="第一卷")
    target = _make_volume(volume_id="vol-2", order=2, title="第二卷")
    chapter = _make_chapter(order=2, volume_id="vol-1")
    moved = _make_chapter(order=4, volume_id="vol-2")
    tool = MoveChapterToVolumeTool(_state=_make_state())

    with patch(
        "app.agent_runtime.tools.impls.chapter.move_chapter_to_volume.create_session"
    ) as mock_cs:
        mock_session = AsyncMock()
        mock_cs.return_value = mock_session
        with patch(
            "app.agent_runtime.tools.impls.chapter.move_chapter_to_volume.volume_repo.list_by_project",
            AsyncMock(return_value=[source, target]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.move_chapter_to_volume.chapter_repo.list_by_volume",
            AsyncMock(return_value=[chapter]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.move_chapter_to_volume.chapter_service.move_chapter_to_volume",
            AsyncMock(return_value=moved),
        ) as move_chapter, patch(
            "app.agent_runtime.tools.impls.chapter.move_chapter_to_volume.record_chapter_diffs",
            AsyncMock(return_value=["chap-1"]),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.move_chapter_to_volume.record_agent_activity_for_change",
            AsyncMock(),
        ), patch(
            "app.agent_runtime.tools.impls.chapter.move_chapter_to_volume.refresh_project_stats",
            AsyncMock(),
        ):
            with patch(
                "app.agent_runtime.tools.impls.chapter.move_chapter_to_volume.chapter_repo.list_by_project",
                AsyncMock(side_effect=[[chapter], [moved]]),
            ):
                result = await tool.ainvoke(
                    {
                        "volume_ref": {"type": "order", "value": 1},
                        "chapter_ref": {"type": "order", "value": 2},
                        "target_volume_ref": {"type": "title", "value": "第二卷"},
                    }
                )

    data = json.loads(result)
    assert set(data) == {"success", "metadata"}
    assert data["success"] is True
    assert data["metadata"]["chapter_diff"] == {
        "operation": "move",
        "chapter_id": "chap-1",
        "chapter_title": "第一章",
        "order": 4,
        "volume_id": "vol-2",
    }
    move_chapter.assert_awaited_once_with(
        mock_session,
        "chap-1",
        "vol-2",
        record_activity=False,
    )
