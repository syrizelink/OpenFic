"""Uji proyeksi perubahan sesi Agent."""

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
from app.storage.models.revision import Revision


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
        message="Pesan pengguna",
        revision_type="agent",
        status=status,
        user_message_id=user_message_id,
        user_message_seq=user_message_seq,
        project_snapshot_title="Proyek",
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
        content="Jalankan perubahan",
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
                "chapter_title": "Bab",
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
                content=_chapter_result("chapter-primary", "dari primary"),
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
                content=_chapter_result("chapter-1", "dari writer"),
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
                content=_chapter_result("chapter-1", "Putaran pertama"),
                tool_name="edit_chapter",
                tool_call_id="child-call-1",
            ),
            _message(
                message_id="child-tool-2",
                session_id="thread-child-1",
                role="tool",
                seq=4,
                content=_chapter_result("chapter-2", "Putaran kedua"),
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
    assert [turn.changes.items[0].title for turn in result.turns] == ["Bab", "Bab"]
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
                content=_chapter_result("chapter-latest", "Permintaan terbaru"),
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
                content=_chapter_result("chapter-1", "Kali pertama"),
                tool_name="edit_chapter",
                tool_call_id="child-call-1",
            ),
            _message(
                message_id="child-tool-2",
                session_id="thread-child-1",
                role="tool",
                seq=2,
                content=_chapter_result("chapter-1", "Kali kedua"),
                tool_name="edit_chapter",
                tool_call_id="child-call-2",
            ),
            _message(
                message_id="child-tool-3",
                session_id="thread-child-1",
                role="tool",
                seq=3,
                content=_chapter_result("chapter-2", "Gagal", success=False),
                tool_name="edit_chapter",
                tool_call_id="child-call-3",
            ),
            _message(
                message_id="child-tool-4",
                session_id="thread-child-1",
                role="tool",
                seq=4,
                content=_chapter_result("chapter-3", "Pratinjau", reason="approval_preview"),
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
    create_payload = json.loads(_chapter_result("chapter-1", "Baris pertama\nBaris kedua\nBaris ketiga"))
    create_payload["metadata"]["chapter_diff"]["operation"] = "create"
    create_payload["metadata"]["chapter_diff"]["sections"][0]["lines"] = [
        {
            "type": "added",
            "before_line_number": None,
            "after_line_number": index,
            "text": text,
        }
        for index, text in enumerate(("Baris pertama", "Baris kedua", "Baris ketiga"), start=1)
    ]
    create_result = json.dumps(create_payload, ensure_ascii=False)
    update_result = json.dumps(
        {
            "success": True,
            "metadata": {
                "chapter_diff": {
                    "operation": "update",
                    "chapter_id": "chapter-1",
                    "chapter_title": "Bab",
                    "sections": [
                        {
                            "type": "content",
                            "lines": [
                                {
                                    "type": "removed",
                                    "before_line_number": 2,
                                    "after_line_number": None,
                                    "text": "Baris kedua",
                                },
                                {
                                    "type": "added",
                                    "before_line_number": None,
                                    "after_line_number": 2,
                                    "text": "Baris kedua setelah diubah",
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
    final_update_lines[0]["text"] = "Baris kedua setelah diubah"
    final_update_lines[1]["text"] = "Baris kedua final"
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
        "Baris pertama",
        "Baris kedua setelah diubah",
        "Baris ketiga",
    ]
    second_request_item = result.turns[0].subagent_runs[1].changes.items[0]
    assert second_request_item.added == 1
    assert second_request_item.removed == 1
    assert [line.text for line in second_request_item.sections[0].lines] == [
        "Baris kedua setelah diubah",
        "Baris kedua final",
    ]
    turn_item = result.turns[0].changes.items[0]
    assert turn_item.added == 3
    assert turn_item.removed == 0
    assert [line.text for line in turn_item.sections[0].lines] == [
        "Baris pertama",
        "Baris kedua final",
        "Baris ketiga",
    ]
    session_item = result.session_changes.items[0]
    assert session_item.added == 3
    assert session_item.removed == 0
    assert [line.text for line in session_item.sections[0].lines] == [
        "Baris pertama",
        "Baris kedua final",
        "Baris ketiga",
    ]


def test_session_total_uses_one_net_diff_for_created_then_updated_note():
    create_result = json.dumps(
        {
            "success": True,
            "metadata": {
                "note_diff": {
                    "operation": "create",
                    "note_id": "note-1",
                    "note_title": "Catatan",
                    "sections": [
                        {
                            "type": "content",
                            "lines": [
                                {
                                    "type": "added",
                                    "before_line_number": None,
                                    "after_line_number": 1,
                                    "text": "Isi awal",
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
                    "note_title": "Catatan",
                    "sections": [
                        {
                            "type": "content",
                            "lines": [
                                {
                                    "type": "context",
                                    "before_line_number": 1,
                                    "after_line_number": 1,
                                    "text": "Isi awal",
                                },
                                {
                                    "type": "added",
                                    "before_line_number": None,
                                    "after_line_number": 2,
                                    "text": "Isi setelah diubah",
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
    assert [line.text for line in item.sections[0].lines] == ["Isi awal", "Isi setelah diubah"]
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
                                "chapter_title": "Judul Baru",
                                "sections": [
                                    {
                                        "type": "title",
                                        "lines": [
                                            {
                                                "type": "removed",
                                                "before_line_number": 1,
                                                "after_line_number": None,
                                                "text": "Judul Lama",
                                            },
                                            {
                                                "type": "added",
                                                "before_line_number": None,
                                                "after_line_number": 1,
                                                "text": "Judul Baru",
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
    assert item.title_before == "Judul Lama"
    assert item.title_after == "Judul Baru"


def test_projects_each_supported_editable_entity_kind():
    metadata = {
        "chapter_diff": {"chapter_id": "chapter-1", "chapter_title": "Bab"},
        "note_diff": {"note_id": "note-1", "note_title": "Catatan"},
        "world_entry_diff": {"entry_id": "entry-1", "entry_title": "Entri"},
        "character_diff": {"character_id": "character-1", "character_name": "Tokoh"},
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
                                "chapter_title": "Bab 1 xx",
                                "path": ["Volume 1"],
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

    assert result.session_changes.items[0].path == ["Volume 1"]


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
                                "note_title": "Catatan",
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
            content=_chapter_result("chapter-1", "dari child"),
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
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [child_request])),
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [_revision("revision-1", "user-1", 0)])),
    ]
    db_session = SimpleNamespace(execute=AsyncMock(side_effect=execute_results))

    async def list_messages(_session, session_id: str):
        return parent_messages if session_id == "parent-session" else child_messages

    async def list_children(_session, session_ids: list[str]):
        return [child_run] if "parent-session" in session_ids else []

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
        "app.agent_runtime.session_changes.list_child_runs_for_parents",
        side_effect=list_children,
    ) as list_children_batch:
        result = await load_agent_session_changes(db_session, "parent-session")

    assert result.session_changes.item_count == 1
    assert result.turns[0].subagent_runs[0].child_run_id == "child-1"
    assert list_messages_batch.call_count == 1
    assert list_children_batch.call_count == 2
