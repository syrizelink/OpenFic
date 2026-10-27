"""Agent 会话变更投影测试。"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent_runtime.session_changes import (
    build_agent_changes,
    load_agent_session_changes,
)
from app.agent_runtime.persistence.model import (
    AgentChildRun,
    AgentChildRunRequest,
    AgentRunMessage,
)
from app.agent_runtime.tools.impls.chapter.diff_preview import (
    ChapterPreviewData,
    build_chapter_diff_preview,
)
from app.storage.models.project import Project
from app.storage.models.revision import Revision
from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot
from app.storage.models.task import Task


def _message(
    *,
    message_id: str,
    session_id: str,
    role: str,
    seq: int,
    content: str = "",
    metadata: dict | None = None,
    tool_name: str | None = None,
    tool_call_id: str | None = None,
    status: str = "complete",
) -> AgentRunMessage:
    return AgentRunMessage(
        id=message_id,
        session_id=session_id,
        task_id="task-1",
        project_id="project-1",
        role=role,
        status=status,
        content=content,
        message_metadata=json.dumps(metadata or {}, ensure_ascii=False),
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        seq=seq,
    )


def _revision(
    revision_id: str,
    user_message_id: str,
    user_message_seq: int,
    *,
    status: str = "completed",
) -> Revision:
    return Revision(
        id=revision_id,
        project_id="project-1",
        task_id="task-1",
        agent_session_id="parent-session",
        message="用户消息",
        revision_type="agent",
        status=status,
        user_message_id=user_message_id,
        user_message_seq=user_message_seq,
        project_snapshot_title="项目",
    )


def _child_run(child_run_id: str = "child-1") -> AgentChildRun:
    return AgentChildRun(
        id=child_run_id,
        parent_session_id="parent-session",
        parent_task_id="task-1",
        parent_thread_id="parent-session",
        child_thread_id=f"thread-{child_run_id}",
        agent_key="writer",
        dispatch_id=f"dispatch-{child_run_id}",
        tool_call_id=f"dispatch-call-{child_run_id}",
        status="completed",
    )


def _child_request(
    child_run_id: str,
    *,
    request_id: str,
    seq: int,
    message_seq: int,
    revision_id: str,
    status: str = "completed",
) -> AgentChildRunRequest:
    return AgentChildRunRequest(
        id=request_id,
        child_run_id=child_run_id,
        parent_session_id="parent-session",
        parent_task_id="task-1",
        request_kind="dispatch" if seq == 0 else "notify",
        content="执行修改",
        parent_revision_id=revision_id,
        child_user_message_id=f"child-user-{request_id}",
        child_user_message_seq=message_seq,
        seq=seq,
        status=status,
    )


def _chapter_result(chapter_id: str, text: str, *, success: bool = True, reason: str | None = None) -> str:
    result = {
        "success": success,
        "metadata": {
            "chapter_diff": {
                "operation": "update",
                "chapter_id": chapter_id,
                "chapter_title": "章节",
                "sections": [
                    {
                        "type": "content",
                        "lines": [
                            {
                                "type": "added",
                                "before_line_number": None,
                                "after_line_number": 1,
                                "text": text,
                            }
                        ],
                    }
                ],
            }
        },
    }
    if reason is not None:
        result["reason"] = reason
    return json.dumps(result, ensure_ascii=False)


def test_includes_subagent_changes_in_parent_turn_and_session_summary():
    result = build_agent_changes(
        "parent-session",
        parent_messages=[
            _message(
                message_id="user-1",
                session_id="parent-session",
                role="user",
                seq=0,
                metadata={"revision_id": "revision-1"},
            ),
            _message(
                message_id="parent-tool-1",
                session_id="parent-session",
                role="tool",
                seq=1,
                content=_chapter_result("chapter-primary", "来自 primary"),
                tool_name="edit_chapter",
                tool_call_id="parent-call-1",
            ),
        ],
        child_runs=[_child_run()],
        child_requests=[
            _child_request(
                "child-1",
                request_id="request-1",
                seq=0,
                message_seq=0,
                revision_id="revision-1",
            )
        ],
        child_messages=[
            _message(
                message_id="child-tool-1",
                session_id="thread-child-1",
                role="tool",
                seq=1,
                content=_chapter_result("chapter-1", "来自 writer"),
                tool_name="edit_chapter",
                tool_call_id="child-call-1",
            )
        ],
        revisions=[_revision("revision-1", "user-1", 0)],
    )

    assert len(result.turns) == 1
    turn = result.turns[0]
    assert turn.revision_id == "revision-1"
    assert turn.changes.item_count == 2
    assert len(turn.subagent_runs) == 1
    assert turn.subagent_runs[0].child_run_id == "child-1"
    assert turn.subagent_runs[0].child_user_message_id == "child-user-request-1"
    assert turn.subagent_runs[0].changes.items[0].agent_key == "writer"
    assert result.session_changes.item_count == 2
    assert any(item.child_run_id == "child-1" for item in result.session_changes.items)


def test_summary_projection_skips_diff_sections():
    result = build_agent_changes(
        "parent-session",
        parent_messages=[
            _message(
                message_id="user-1",
                session_id="parent-session",
                role="user",
                seq=0,
                metadata={"revision_id": "revision-1"},
            ),
            _message(
                message_id="tool-1",
                session_id="parent-session",
                role="tool",
                seq=1,
                content=_chapter_result("chapter-1", "新增正文"),
                tool_name="edit_chapter",
                tool_call_id="tool-call-1",
            ),
        ],
        child_runs=[],
        child_requests=[],
        child_messages=[],
        revisions=[_revision("revision-1", "user-1", 0)],
        include_details=False,
    )

    item = result.session_changes.items[0]
    assert item.sections == []
    assert "sections" not in result.to_payload(include_details=False)["session_changes"]["items"][0]


def test_assigns_reused_subagent_requests_to_their_parent_turns():
    child_run = _child_run()
    result = build_agent_changes(
        "parent-session",
        parent_messages=[
            _message(
                message_id="user-1",
                session_id="parent-session",
                role="user",
                seq=0,
                metadata={"revision_id": "revision-1"},
            ),
            _message(
                message_id="user-2",
                session_id="parent-session",
                role="user",
                seq=4,
                metadata={"revision_id": "revision-2"},
            ),
        ],
        child_runs=[child_run],
        child_requests=[
            _child_request(
                "child-1",
                request_id="request-1",
                seq=0,
                message_seq=0,
                revision_id="revision-1",
            ),
            _child_request(
                "child-1",
                request_id="request-2",
                seq=1,
                message_seq=3,
                revision_id="revision-2",
            ),
        ],
        child_messages=[
            _message(
                message_id="child-tool-1",
                session_id="thread-child-1",
                role="tool",
                seq=1,
                content=_chapter_result("chapter-1", "第一轮"),
                tool_name="edit_chapter",
                tool_call_id="child-call-1",
            ),
            _message(
                message_id="child-tool-2",
                session_id="thread-child-1",
                role="tool",
                seq=4,
                content=_chapter_result("chapter-2", "第二轮"),
                tool_name="edit_chapter",
                tool_call_id="child-call-2",
            ),
        ],
        revisions=[
            _revision("revision-1", "user-1", 0),
            _revision("revision-2", "user-2", 4),
        ],
    )

    assert [turn.revision_id for turn in result.turns] == ["revision-1", "revision-2"]
    assert [turn.changes.items[0].title for turn in result.turns] == ["章节", "章节"]
    assert [
        turn.subagent_runs[0].changes.items[0].key for turn in result.turns
    ] == ["chapter:chapter-1", "chapter:chapter-2"]
    assert result.session_changes.item_count == 2


def test_uses_latest_request_when_child_message_sequence_is_reused():
    result = build_agent_changes(
        "parent-session",
        parent_messages=[],
        child_runs=[_child_run()],
        child_requests=[
            _child_request(
                "child-1",
                request_id="request-old",
                seq=0,
                message_seq=0,
                revision_id="revision-old",
            ),
            _child_request(
                "child-1",
                request_id="request-cancelled",
                seq=1,
                message_seq=3,
                revision_id="revision-rolled-back",
                status="cancelled",
            ),
            _child_request(
                "child-1",
                request_id="request-stale",
                seq=2,
                message_seq=5,
                revision_id="revision-stale",
                status="cancelled",
            ),
            _child_request(
                "child-1",
                request_id="request-latest",
                seq=3,
                message_seq=3,
                revision_id="revision-latest",
            ),
        ],
        child_messages=[
            _message(
                message_id="child-tool-latest",
                session_id="thread-child-1",
                role="tool",
                seq=6,
                content=_chapter_result("chapter-latest", "最新请求"),
                tool_name="edit_chapter",
                tool_call_id="child-call-latest",
            )
        ],
        revisions=[
            _revision("revision-old", "user-old", 0),
            _revision("revision-rolled-back", "user-rolled-back", 1, status="rolled_back"),
            _revision("revision-stale", "user-stale", 2, status="rolled_back"),
            _revision("revision-latest", "user-latest", 3),
        ],
    )

    latest_turn = next(turn for turn in result.turns if turn.revision_id == "revision-latest")
    assert latest_turn.changes.item_count == 1
    assert latest_turn.subagent_runs[0].request_id == "request-latest"


def test_merges_repeated_entity_changes_and_ignores_failed_or_preview_results():
    result = build_agent_changes(
        "parent-session",
        parent_messages=[
            _message(
                message_id="user-1",
                session_id="parent-session",
                role="user",
                seq=0,
                metadata={"revision_id": "revision-1"},
            )
        ],
        child_runs=[_child_run()],
        child_requests=[
            _child_request(
                "child-1",
                request_id="request-1",
                seq=0,
                message_seq=0,
                revision_id="revision-1",
            )
        ],
        child_messages=[
            _message(
                message_id="child-tool-1",
                session_id="thread-child-1",
                role="tool",
                seq=1,
                content=_chapter_result("chapter-1", "第一次"),
                tool_name="edit_chapter",
                tool_call_id="child-call-1",
            ),
            _message(
                message_id="child-tool-2",
                session_id="thread-child-1",
                role="tool",
                seq=2,
                content=_chapter_result("chapter-1", "第二次"),
                tool_name="edit_chapter",
                tool_call_id="child-call-2",
            ),
            _message(
                message_id="child-tool-3",
                session_id="thread-child-1",
                role="tool",
                seq=3,
                content=_chapter_result("chapter-2", "失败", success=False),
                tool_name="edit_chapter",
                tool_call_id="child-call-3",
            ),
            _message(
                message_id="child-tool-4",
                session_id="thread-child-1",
                role="tool",
                seq=4,
                content=_chapter_result("chapter-3", "预览", reason="approval_preview"),
                tool_name="edit_chapter",
                tool_call_id="child-call-4",
            ),
        ],
        revisions=[_revision("revision-1", "user-1", 0)],
    )

    assert result.session_changes.item_count == 1
    item = result.session_changes.items[0]
    assert item.key == "chapter:chapter-1"
    assert len(item.sections) == 1
    assert sum(len(section.lines) for section in item.sections) == 1


def test_keeps_full_created_chapter_content_after_partial_update():
    create_payload = json.loads(_chapter_result("chapter-1", "第一行\n第二行\n第三行"))
    create_payload["metadata"]["chapter_diff"]["operation"] = "create"
    create_payload["metadata"]["chapter_diff"]["sections"][0]["lines"] = [
        {
            "type": "added",
            "before_line_number": None,
            "after_line_number": index,
            "text": text,
        }
        for index, text in enumerate(("第一行", "第二行", "第三行"), start=1)
    ]
    create_result = json.dumps(create_payload, ensure_ascii=False)
    update_result = json.dumps(
        {
            "success": True,
            "metadata": {
                "chapter_diff": {
                    "operation": "update",
                    "chapter_id": "chapter-1",
                    "chapter_title": "章节",
                    "sections": [
                        {
                            "type": "content",
                            "lines": [
                                {
                                    "type": "removed",
                                    "before_line_number": 2,
                                    "after_line_number": None,
                                    "text": "第二行",
                                },
                                {
                                    "type": "added",
                                    "before_line_number": None,
                                    "after_line_number": 2,
                                    "text": "修改后的第二行",
                                },
                            ],
                        }
                    ],
                }
            },
        },
        ensure_ascii=False,
    )
    final_update_payload = json.loads(update_result)
    final_update_lines = final_update_payload["metadata"]["chapter_diff"]["sections"][0]["lines"]
    final_update_lines[0]["text"] = "修改后的第二行"
    final_update_lines[1]["text"] = "最终的第二行"
    final_update_result = json.dumps(final_update_payload, ensure_ascii=False)
    result = build_agent_changes(
        "parent-session",
        parent_messages=[
            _message(
                message_id="user-1",
                session_id="parent-session",
                role="user",
                seq=0,
                metadata={"revision_id": "revision-1"},
            )
        ],
        child_runs=[_child_run()],
        child_requests=[
            _child_request(
                "child-1",
                request_id="request-1",
                seq=0,
                message_seq=0,
                revision_id="revision-1",
            ),
            _child_request(
                "child-1",
                request_id="request-2",
                seq=1,
                message_seq=3,
                revision_id="revision-1",
            ),
        ],
        child_messages=[
            _message(
                message_id="child-tool-create",
                session_id="thread-child-1",
                role="tool",
                seq=1,
                content=create_result,
                tool_name="write_chapter",
                tool_call_id="child-call-create",
            ),
            _message(
                message_id="child-tool-update",
                session_id="thread-child-1",
                role="tool",
                seq=2,
                content=update_result,
                tool_name="edit_chapter",
                tool_call_id="child-call-update",
            ),
            _message(
                message_id="child-tool-final-update",
                session_id="thread-child-1",
                role="tool",
                seq=3,
                content=final_update_result,
                tool_name="edit_chapter",
                tool_call_id="child-call-final-update",
            ),
        ],
        revisions=[_revision("revision-1", "user-1", 0)],
    )

    first_request_item = result.turns[0].subagent_runs[0].changes.items[0]
    assert first_request_item.operation == "create"
    assert first_request_item.added == 3
    assert first_request_item.removed == 0
    assert [line.text for line in first_request_item.sections[0].lines] == [
        "第一行",
        "修改后的第二行",
        "第三行",
    ]
    second_request_item = result.turns[0].subagent_runs[1].changes.items[0]
    assert second_request_item.added == 1
    assert second_request_item.removed == 1
    assert [line.text for line in second_request_item.sections[0].lines] == [
        "修改后的第二行",
        "最终的第二行",
    ]
    turn_item = result.turns[0].changes.items[0]
    assert turn_item.added == 3
    assert turn_item.removed == 0
    assert [line.text for line in turn_item.sections[0].lines] == [
        "第一行",
        "最终的第二行",
        "第三行",
    ]
    session_item = result.session_changes.items[0]
    assert session_item.added == 3
    assert session_item.removed == 0
    assert [line.text for line in session_item.sections[0].lines] == [
        "第一行",
        "最终的第二行",
        "第三行",
    ]


def test_session_total_uses_one_net_diff_for_created_then_updated_note():
    create_result = json.dumps(
        {
            "success": True,
            "metadata": {
                "note_diff": {
                    "operation": "create",
                    "note_id": "note-1",
                    "note_title": "笔记",
                    "sections": [
                        {
                            "type": "content",
                            "lines": [
                                {
                                    "type": "added",
                                    "before_line_number": None,
                                    "after_line_number": 1,
                                    "text": "初始内容",
                                }
                            ],
                        }
                    ],
                }
            },
        },
        ensure_ascii=False,
    )
    update_result = json.dumps(
        {
            "success": True,
            "metadata": {
                "note_diff": {
                    "operation": "update",
                    "note_id": "note-1",
                    "note_title": "笔记",
                    "sections": [
                        {
                            "type": "content",
                            "lines": [
                                {
                                    "type": "context",
                                    "before_line_number": 1,
                                    "after_line_number": 1,
                                    "text": "初始内容",
                                },
                                {
                                    "type": "added",
                                    "before_line_number": None,
                                    "after_line_number": 2,
                                    "text": "修改后的内容",
                                },
                            ],
                        }
                    ],
                }
            },
        },
        ensure_ascii=False,
    )
    result = build_agent_changes(
        "parent-session",
        parent_messages=[
            _message(
                message_id="user-1",
                session_id="parent-session",
                role="user",
                seq=0,
                metadata={"revision_id": "revision-1"},
            ),
            _message(
                message_id="tool-create",
                session_id="parent-session",
                role="tool",
                seq=1,
                content=create_result,
                tool_name="write_note",
                tool_call_id="call-create",
            ),
            _message(
                message_id="tool-update",
                session_id="parent-session",
                role="tool",
                seq=2,
                content=update_result,
                tool_name="edit_note",
                tool_call_id="call-update",
            ),
        ],
        child_runs=[],
        child_requests=[],
        child_messages=[],
        revisions=[_revision("revision-1", "user-1", 0)],
    )

    assert result.session_changes.item_count == 1
    item = result.session_changes.items[0]
    assert item.operation == "create"
    assert len(item.sections) == 1
    assert [line.type for line in item.sections[0].lines] == ["added", "added"]
    assert [line.text for line in item.sections[0].lines] == ["初始内容", "修改后的内容"]
    assert item.added == 2
    assert item.removed == 0


def test_title_only_change_is_not_counted_as_line_diff():
    result = build_agent_changes(
        "parent-session",
        parent_messages=[
            _message(
                message_id="user-1",
                session_id="parent-session",
                role="user",
                seq=0,
                metadata={"revision_id": "revision-1"},
            ),
            _message(
                message_id="tool-1",
                session_id="parent-session",
                role="tool",
                seq=1,
                content=json.dumps(
                    {
                        "success": True,
                        "metadata": {
                            "chapter_diff": {
                                "operation": "update",
                                "chapter_id": "chapter-1",
                                "chapter_title": "新标题",
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
                    },
                    ensure_ascii=False,
                ),
                tool_name="edit_chapter",
                tool_call_id="call-1",
            ),
        ],
        child_runs=[],
        child_requests=[],
        child_messages=[],
        revisions=[_revision("revision-1", "user-1", 0)],
    )

    item = result.session_changes.items[0]
    assert item.sections == []
    assert item.added == 0
    assert item.removed == 0
    assert item.title_before == "旧标题"
    assert item.title_after == "新标题"


def test_projects_each_supported_editable_entity_kind():
    metadata = {
        "chapter_diff": {"chapter_id": "chapter-1", "chapter_title": "章节"},
        "note_diff": {"note_id": "note-1", "note_title": "笔记"},
        "world_entry_diff": {"entry_id": "entry-1", "entry_title": "条目"},
        "character_diff": {"character_id": "character-1", "character_name": "角色"},
    }
    result = build_agent_changes(
        "parent-session",
        parent_messages=[
            _message(
                message_id="user-1",
                session_id="parent-session",
                role="user",
                seq=0,
                metadata={"revision_id": "revision-1"},
            ),
            _message(
                message_id="parent-tool-1",
                session_id="parent-session",
                role="tool",
                seq=1,
                content=json.dumps({"success": True, "metadata": metadata}, ensure_ascii=False),
                tool_name="edit_content",
                tool_call_id="parent-call-1",
            ),
        ],
        child_runs=[],
        child_requests=[],
        child_messages=[],
        revisions=[_revision("revision-1", "user-1", 0)],
    )

    assert {item.kind for item in result.session_changes.items} == {
        "chapter",
        "note",
        "world_entry",
        "character",
    }


def test_preserves_change_item_path_from_tool_metadata():
    result = build_agent_changes(
        "parent-session",
        parent_messages=[
            _message(
                message_id="user-1",
                session_id="parent-session",
                role="user",
                seq=0,
                metadata={"revision_id": "revision-1"},
            ),
            _message(
                message_id="parent-tool-1",
                session_id="parent-session",
                role="tool",
                seq=1,
                content=json.dumps(
                    {
                        "success": True,
                        "metadata": {
                            "chapter_diff": {
                                "operation": "update",
                                "chapter_id": "chapter-1",
                                "chapter_title": "第一章 xx",
                                "path": ["第一卷"],
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                tool_name="edit_chapter",
                tool_call_id="parent-call-1",
            ),
        ],
        child_runs=[],
        child_requests=[],
        child_messages=[],
        revisions=[_revision("revision-1", "user-1", 0)],
    )

    assert result.session_changes.items[0].path == ["第一卷"]


def test_keeps_executed_changes_from_cancelled_revision():
    result = build_agent_changes(
        "parent-session",
        parent_messages=[
            _message(
                message_id="user-1",
                session_id="parent-session",
                role="user",
                seq=0,
                metadata={"revision_id": "revision-1"},
            )
        ],
        child_runs=[_child_run()],
        child_requests=[
            _child_request(
                "child-1",
                request_id="request-1",
                seq=0,
                message_seq=0,
                revision_id="revision-1",
            )
        ],
        child_messages=[
            _message(
                message_id="child-tool-1",
                session_id="thread-child-1",
                role="tool",
                seq=1,
                content=json.dumps(
                    {
                        "success": True,
                        "metadata": {
                            "note_diff": {
                                "operation": "update",
                                "note_id": "note-1",
                                "note_title": "笔记",
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                tool_name="edit_note",
                tool_call_id="child-call-1",
            )
        ],
        revisions=[_revision("revision-1", "user-1", 0, status="cancelled")],
    )

    assert result.session_changes.item_count == 1
    assert result.turns[0].changes.items[0].kind == "note"


@pytest.mark.asyncio
async def test_loads_only_requested_revision_range(
    session,
):
    session.add_all(
        [
            Project(id="project-1", title="测试项目"),
            Task(
                id="task-1",
                project_id="project-1",
                title="测试任务",
                mode="agent",
                agent_session_id="parent-session",
            ),
        ]
    )
    await session.flush()
    session.add_all(
        [
            _message(
                message_id="user-1",
                session_id="parent-session",
                role="user",
                seq=0,
                metadata={"revision_id": "revision-1"},
            ),
            _message(
                message_id="tool-1",
                session_id="parent-session",
                role="tool",
                seq=1,
                content=_chapter_result("chapter-1", "第一轮"),
                tool_name="edit_chapter",
                tool_call_id="tool-call-1",
            ),
            _message(
                message_id="user-2",
                session_id="parent-session",
                role="user",
                seq=2,
                metadata={"revision_id": "revision-2"},
            ),
            _message(
                message_id="tool-2",
                session_id="parent-session",
                role="tool",
                seq=3,
                content=_chapter_result("chapter-2", "第二轮"),
                tool_name="edit_chapter",
                tool_call_id="tool-call-2",
            ),
            _revision("revision-1", "user-1", 0),
            _revision("revision-2", "user-2", 2),
        ]
    )
    await session.flush()

    session.add(RevisionChapterSnapshot(
        revision_id="revision-1", chapter_id="chapter-1", project_id="project-1",
        exists=True, title="章节", content="原有正文\n\n",
    ))
    await session.flush()

    result = await load_agent_session_changes(
        session,
        "parent-session",
        revision_id="revision-1",
    )

    assert [turn.revision_id for turn in result.turns] == ["revision-1"]
    assert [item.key for item in result.session_changes.items] == ["chapter:chapter-1"]
    assert [line.text for line in result.session_changes.items[0].sections[0].lines] == [
        "第一轮", "原有正文", ""
    ]


@pytest.mark.asyncio
async def test_loads_parent_and_descendant_messages_before_projecting_changes():
    child_run = _child_run()
    parent_messages = [
        _message(
            message_id="user-1",
            session_id="parent-session",
            role="user",
            seq=0,
            metadata={"revision_id": "revision-1"},
        )
    ]
    child_messages = [
        _message(
            message_id="child-tool-1",
            session_id="thread-child-1",
            role="tool",
            seq=1,
            content=_chapter_result("chapter-1", "来自 child"),
            tool_name="edit_chapter",
            tool_call_id="child-call-1",
        )
    ]
    child_request = _child_request(
        "child-1",
        request_id="request-1",
        seq=0,
        message_seq=0,
        revision_id="revision-1",
    )
    execute_results = [
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [_revision("revision-1", "user-1", 0)])),
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [child_request])),
    ]
    db_session = SimpleNamespace(execute=AsyncMock(side_effect=execute_results))

    async def list_messages(_session, session_id: str):
        return parent_messages if session_id == "parent-session" else child_messages

    async def list_children(_session, session_id: str):
        return [child_run] if session_id == "parent-session" else []

    with patch(
        "app.agent_runtime.session_changes.message_repo.list_by_session",
        side_effect=list_messages,
    ), patch(
        "app.agent_runtime.session_changes.message_repo.list_by_sessions",
        return_value={
            "parent-session": parent_messages,
            "thread-child-1": child_messages,
        },
    ) as list_messages_batch, patch(
        "app.agent_runtime.session_changes.list_descendant_child_runs",
        side_effect=list_children,
    ) as list_children_batch, patch(
        "app.agent_runtime.session_changes.revision_chapter_snapshot_repo.list_by_revisions",
        AsyncMock(return_value=[]),
    ) as list_snapshots:
        result = await load_agent_session_changes(db_session, "parent-session")

    assert result.session_changes.item_count == 1
    assert result.turns[0].subagent_runs[0].child_run_id == "child-1"
    assert list_messages_batch.call_count == 1
    list_children_batch.assert_awaited_once_with(db_session, "parent-session")
    list_snapshots.assert_awaited_once_with(db_session, ["revision-1"])


@pytest.mark.parametrize("include_details", [False, True])
def test_summary_applies_partial_chapter_diffs_to_revision_snapshot(include_details: bool) -> None:
    original = "乙章原始内容。\n\n乙章原始结尾。\n"
    steps = [
        [("removed", 1, "乙章原始内容。"), ("added", 1, "乙章第一次改动后的开头。")],
        [("removed", 3, "乙章原始结尾。"), ("added", 3, "乙章第五次改动。")],
        [("removed", 1, "乙章第一次改动后的开头。"), ("added", 1, "乙章整篇重置后的内容。"),
         ("removed", 3, "乙章第五次改动。"), ("added", 3, "用于验证整段替换。")],
    ]
    messages = [_message(message_id="user-1", session_id="parent-session", role="user", seq=0)]
    for index, step in enumerate(steps, 1):
        payload = json.loads(_chapter_result("chapter-1", ""))
        payload["metadata"]["chapter_diff"]["sections"][0]["lines"] = [
            {"type": kind, "before_line_number": number if kind == "removed" else None,
             "after_line_number": number if kind == "added" else None, "text": text}
            for kind, number, text in step
        ]
        messages.append(_message(
            message_id=f"tool-{index}", session_id="parent-session", role="tool", seq=index,
            content=json.dumps(payload), tool_name="edit_chapter",
        ))
    result = build_agent_changes(
        "parent-session",
        parent_messages=messages,
        child_runs=[],
        child_requests=[],
        child_messages=[],
        revisions=[_revision("revision-1", "user-1", 0)],
        chapter_snapshots=[RevisionChapterSnapshot(
            revision_id="revision-1", chapter_id="chapter-1", project_id="project-1",
            exists=True, title="章节", content=original,
        )],
        include_details=include_details,
    )
    for summary in (result.turns[0].changes, result.session_changes):
        assert (summary.added, summary.removed) == (2, 2)
        if include_details:
            lines = summary.items[0].sections[0].lines
            assert [(line.after_line_number, line.text) for line in lines if line.type != "removed"] == [
                (1, "乙章整篇重置后的内容。"), (2, ""), (3, "用于验证整段替换。")
            ]
        else:
            assert summary.items[0].sections == []


@pytest.mark.parametrize("rename_after_edit", [False, True])
@pytest.mark.parametrize("existing_blank_lines", [0, 1, 2])
def test_chapter_diff_preserves_blank_lines_after_edit_and_rename(
    existing_blank_lines: int, rename_after_edit: bool
) -> None:
    before = ChapterPreviewData(
        id="chapter-1",
        project_id="project-1",
        volume_id="volume-1",
        title="测试章节乙",
        content="乙章原始内容。" + ("\n" * (existing_blank_lines + 1) if existing_blank_lines else ""),
    )
    blank_lines = max(existing_blank_lines, 1)
    after = ChapterPreviewData(
        id=before.id,
        project_id=before.project_id,
        volume_id=before.volume_id,
        title=before.title,
        content="乙章整篇重置后的内容。" + "\n" * (blank_lines + 1) + "用于验证整段替换。",
    )
    diffs = [build_chapter_diff_preview(before, after)]
    if rename_after_edit:
        renamed = ChapterPreviewData(
            id=after.id,
            project_id=after.project_id,
            volume_id=after.volume_id,
            title="测试章节乙改名",
            content=after.content,
        )
        diffs.append(build_chapter_diff_preview(after, renamed))
    messages = [_message(message_id="user-1", session_id="parent-session", role="user", seq=0)]
    messages.extend(
        _message(
            message_id=f"tool-{index}",
            session_id="parent-session",
            role="tool",
            seq=index,
            content=json.dumps({"success": True, "metadata": {"chapter_diff": diff}}),
            tool_name="edit_chapter",
        )
        for index, diff in enumerate(diffs, 1)
    )
    for include_details in (True, False):
        result = build_agent_changes(
            "parent-session",
            parent_messages=messages,
            child_runs=[],
            child_requests=[],
            child_messages=[],
            revisions=[_revision("revision-1", "user-1", 0)],
            include_details=include_details,
        )
        for summary in (result.turns[0].changes, result.session_changes):
            assert (summary.added, summary.removed) == (2 if existing_blank_lines else 3, 1)
            if not include_details:
                continue
            lines = summary.items[0].sections[0].lines
            after_lines = [line for line in lines if line.type != "removed"]
            assert [line.text for line in after_lines] == [
                "乙章整篇重置后的内容。", *([""] * blank_lines), "用于验证整段替换。"
            ]
            assert [line.after_line_number for line in after_lines] == list(range(1, blank_lines + 3))
            assert [line.type for line in after_lines] == [
                "added", *(["context" if existing_blank_lines else "added"] * blank_lines), "added"
            ]


@pytest.mark.parametrize("rename_before_recreation", [False, True])
def test_deleted_chapter_recreated_at_same_path_has_one_net_diff(rename_before_recreation):
    def chapter_diff(chapter_id, title, operation, before, after, *, old_title=None, path="第一卷"):
        lines = [
            {"type": "removed", "before_line_number": index, "text": text}
            for index, text in enumerate(before, 1)
        ] + [
            {"type": "added", "after_line_number": index, "text": text}
            for index, text in enumerate(after, 1)
        ]
        sections = [{"type": "content", "lines": lines}] if lines else []
        if old_title:
            sections.append({"type": "title", "lines": [
                {"type": "removed", "text": old_title},
                {"type": "added", "text": title},
            ]})
        return json.dumps({"success": True, "metadata": {"chapter_diff": {
            "chapter_id": chapter_id, "chapter_title": title, "path": [path],
            "operation": operation, "sections": sections,
        }}}, ensure_ascii=False)

    created_title = "临时标题" if rename_before_recreation else "章节"
    payloads = [
        chapter_diff("old", "章节", "delete", ["旧内容"], []),
        chapter_diff("new", created_title, "create", [], ["新内容"]),
    ]
    if rename_before_recreation:
        payloads.append(chapter_diff("new", "章节", "update", [], [], old_title=created_title))
    else:
        payloads.append(chapter_diff("new", "新标题", "update", [], [], old_title="章节"))
    payloads.append(chapter_diff("other", "章节", "create", [], ["另一卷"], path="第二卷"))
    messages = [_message(message_id="user-1", session_id="parent-session", role="user", seq=0)]
    messages.extend(
        _message(message_id=f"tool-{index}", session_id="parent-session", role="tool", seq=index,
                 content=payload, tool_name="edit_chapter")
        for index, payload in enumerate(payloads, 1)
    )
    kwargs = dict(parent_messages=messages, child_runs=[], child_requests=[], child_messages=[],
                  revisions=[_revision("revision-1", "user-1", 0)])
    details = build_agent_changes("parent-session", **kwargs)
    summary = build_agent_changes("parent-session", **kwargs, include_details=False)
    for result in (details, summary):
        for changes in (result.turns[0].changes, result.session_changes):
            assert changes.item_count == 2
            item = next(item for item in changes.items if item.path == ["第一卷"])
            assert item.title == ("章节" if rename_before_recreation else "新标题")
            assert (item.added, item.removed) == (1, 1)
    item = details.session_changes.items[0]
    assert [(line.type, line.text) for line in item.sections[0].lines] == [
        ("removed", "旧内容"), ("added", "新内容")
    ]
