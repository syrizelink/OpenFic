"""Task API projection for agent runtime messages."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import repo
from app.agent_runtime.persistence.task_projection import (
    load_task_messages_for_agent_session,
)


@pytest.mark.asyncio
async def test_projects_runtime_messages_to_task_messages(
    db_session: AsyncSession,
    sample_task,
) -> None:
    sid = "session_projection"

    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="续写一段剧情",
        status="sent",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        agent_id="explorer",
        content="需要补充信息",
        reasoning="我需要先确认走向。",
        reasoning_duration_ms=2450,
        status="complete",
        tool_calls=[
            {
                "id": "call_ask",
                "name": "ask_user",
                "args": {"questions": [{"title": "剧情走向？"}]},
            }
        ],
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content='{"success": true, "data": {"answer": "按原著"}}',
        status="complete",
        tool_call_id="call_ask",
        tool_name="ask_user",
    )

    messages = await load_task_messages_for_agent_session(db_session, sid)

    assert [message.message_type for message in messages] == [
        "user_request",
        "reasoning",
        "text",
        None,
        "tool",
    ]
    assert messages[0].role == "user"
    assert messages[0].content == "续写一段剧情"
    assert messages[0].payload == {"kind": "user_request"}
    assert messages[1].content == "我需要先确认走向。"
    assert messages[1].payload == {"kind": "reasoning", "duration_ms": 2450}
    assert messages[2].content == "需要补充信息"
    assert messages[3].tool_calls == [
        {
            "id": "call_ask",
            "name": "ask_user",
            "args": {"questions": [{"title": "剧情走向？"}]},
        }
    ]
    assert messages[4].payload["tool_call_id"] == "call_ask"
    assert messages[4].payload["tool_name"] == "ask_user"
    assert messages[4].payload["tool_args"] == {
        "questions": [{"title": "剧情走向？"}]
    }
    assert messages[4].payload["tool_result"]["data"] == {"answer": "按原著"}


@pytest.mark.asyncio
async def test_projects_node_events_to_hidden_task_messages(
    db_session: AsyncSession,
    sample_task,
) -> None:
    sid = "session_projection"

    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        agent_id="composer",
        message_type="node_start",
        display_channel="hidden",
        metadata={
            "kind": "agent_node",
            "event_type": "node_start",
            "node": "composer",
            "phase": "start",
            "node_status": "running",
            "current_node": "composer",
            "previous_node": "explorer",
        },
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        agent_id="composer",
        message_type="node_end",
        display_channel="hidden",
        metadata={
            "kind": "agent_node",
            "event_type": "node_end",
            "node": "composer",
            "phase": "end",
            "node_status": "completed",
            "current_node": None,
            "previous_node": "explorer",
        },
    )

    messages = await load_task_messages_for_agent_session(db_session, sid)

    assert [message.message_type for message in messages] == ["node_start", "node_end"]
    assert [message.role for message in messages] == ["system", "system"]
    assert [message.display_channel for message in messages] == ["hidden", "hidden"]
    assert [message.message_status for message in messages] == ["running", "completed"]
    assert messages[0].payload == {
        "node": "composer",
        "phase": "start",
        "status": "running",
        "current_node": "composer",
        "previous_node": "explorer",
    }
    assert messages[1].payload == {
        "node": "composer",
        "phase": "end",
        "status": "completed",
        "current_node": None,
        "previous_node": "explorer",
    }


@pytest.mark.asyncio
async def test_projects_compaction_marker_as_display_only_task_message(
    db_session: AsyncSession,
    sample_task,
) -> None:
    sid = "session_projection_compaction"

    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="原始请求",
        status="sent",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        content="已进行压缩",
        status="complete",
        message_type="compaction",
        display_channel="list",
        llm_visibility="hidden",
        metadata={
            "kind": "compaction",
            "compaction_id": "cmp_projection",
            "trigger": "manual",
            "start_seq": 1,
            "end_seq": 4,
            "source_input_tokens": 100,
            "summary_tokens": 10,
        },
        message_id="compaction:cmp_projection",
    )

    messages = await load_task_messages_for_agent_session(db_session, sid)

    assert [message.message_type for message in messages] == [
        "user_request",
        "compaction",
    ]
    compaction_message = messages[1]
    assert compaction_message.id == "compaction:cmp_projection"
    assert compaction_message.role == "system"
    assert compaction_message.content == "已进行压缩"
    assert compaction_message.display_channel == "list"
    assert compaction_message.message_status == "completed"
    assert compaction_message.payload == {"kind": "compaction"}
    assert compaction_message.correlation_id == "compaction:cmp_projection"


@pytest.mark.asyncio
async def test_projection_filters_subagent_internal_rows_from_parent_session(
    db_session: AsyncSession,
    sample_task,
) -> None:
    sid = "session_projection_subagent_leak"

    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        agent_id="primary",
        content="",
        status="complete",
        tool_calls=[
            {
                "id": "dispatch-call",
                "name": "dispatch_subagent",
                "args": {"agent_key": "writer", "task": "write"},
            }
        ],
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content='{"success": true, "status": "completed", "child_run_id": "child-1"}',
        status="complete",
        tool_call_id="dispatch-call",
        tool_name="dispatch_subagent",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        agent_id="writer",
        content="child draft internals",
        status="complete",
        tool_calls=[
            {
                "id": "child-write-call",
                "name": "write_chapter",
                "args": {"title": "chapter draft"},
            }
        ],
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content='{"success": true, "title": "chapter draft"}',
        status="complete",
        tool_call_id="child-write-call",
        tool_name="write_chapter",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        agent_id="writer",
        message_type="node_start",
        display_channel="hidden",
        metadata={
            "kind": "agent_node",
            "event_type": "node_start",
            "node": "writer",
            "phase": "start",
            "node_status": "running",
        },
    )

    messages = await load_task_messages_for_agent_session(db_session, sid)

    assert [message.tool_call_id for message in messages] == [
        None,
        "dispatch-call",
    ]
    assert messages[0].tool_calls == [
        {
            "id": "dispatch-call",
            "name": "dispatch_subagent",
            "args": {"agent_key": "writer", "task": "write"},
        }
    ]
    assert messages[1].message_type == "tool"
    assert messages[1].payload["tool_name"] == "dispatch_subagent"


@pytest.mark.asyncio
async def test_projects_interrupted_ask_user_before_node_end(
    db_session: AsyncSession,
    sample_task,
) -> None:
    sid = "session_interrupted_ask_user_projection"

    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        agent_id="explorer",
        message_type="node_start",
        display_channel="hidden",
        metadata={
            "kind": "agent_node",
            "event_type": "node_start",
            "node": "explorer",
            "phase": "start",
            "node_status": "running",
        },
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        agent_id="explorer",
        content="需要确认方向",
        status="complete",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        agent_id="explorer",
        message_type="node_end",
        display_channel="hidden",
        metadata={
            "kind": "agent_node",
            "event_type": "node_end",
            "node": "explorer",
            "phase": "end",
            "node_status": "error",
        },
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content="[中断] 工具执行未完成",
        status="aborted",
        tool_call_id="call_ask",
        tool_name="ask_user",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        agent_id="explorer",
        message_type="node_start",
        display_channel="hidden",
        metadata={
            "kind": "agent_node",
            "event_type": "node_start",
            "node": "explorer",
            "phase": "start",
            "node_status": "running",
        },
    )

    messages = await load_task_messages_for_agent_session(db_session, sid)

    assert [message.message_type for message in messages] == [
        "node_start",
        "text",
        "tool",
        "node_end",
        "node_start",
    ]
    assert messages[2].payload["tool_name"] == "ask_user"
    assert messages[2].message_status == "error"


@pytest.mark.asyncio
async def test_projects_resumed_tool_call_as_single_tool_message(
    db_session: AsyncSession,
    sample_task,
) -> None:
    sid = "session_resumed_tool_projection"

    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        agent_id="writer",
        message_type="node_start",
        display_channel="hidden",
        metadata={
            "kind": "agent_node",
            "event_type": "node_start",
            "node": "writer",
            "phase": "start",
            "node_status": "running",
        },
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        agent_id="writer",
        content="",
        status="complete",
        tool_calls=[
            {
                "id": "call_write",
                "name": "write_chapter",
                "args": {"title": "第一章"},
            }
        ],
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content="[中断] 工具执行未完成",
        status="aborted",
        tool_call_id="call_write",
        tool_name="write_chapter",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        agent_id="writer",
        message_type="node_end",
        display_channel="hidden",
        metadata={
            "kind": "agent_node",
            "event_type": "node_end",
            "node": "writer",
            "phase": "end",
            "node_status": "error",
        },
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        agent_id="writer",
        message_type="node_start",
        display_channel="hidden",
        metadata={
            "kind": "agent_node",
            "event_type": "node_start",
            "node": "writer",
            "phase": "start",
            "node_status": "running",
        },
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content='{"success": true, "data": {"chapter_id": "chapter_1"}}',
        status="complete",
        tool_call_id="call_write",
        tool_name="write_chapter",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        agent_id="writer",
        message_type="node_end",
        display_channel="hidden",
        metadata={
            "kind": "agent_node",
            "event_type": "node_end",
            "node": "writer",
            "phase": "end",
            "node_status": "completed",
        },
    )

    messages = await load_task_messages_for_agent_session(db_session, sid)

    tool_messages = [message for message in messages if message.message_type == "tool"]

    assert [message.message_type for message in messages] == [
        "node_start",
        None,
        "tool",
        "node_end",
        "node_start",
        "node_end",
    ]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call_write"
    assert tool_messages[0].message_status == "completed"
    assert tool_messages[0].payload["tool_name"] == "write_chapter"
    assert tool_messages[0].payload["tool_args"] == {"title": "第一章"}
    assert tool_messages[0].payload["tool_result"]["success"] is True
    assert tool_messages[0].payload["tool_result"]["data"] == {"chapter_id": "chapter_1"}


@pytest.mark.asyncio
async def test_projects_interrupted_tool_preview_as_completed_tool_message(
    db_session: AsyncSession,
    sample_task,
) -> None:
    sid = "session_interrupted_tool_preview_projection"

    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        agent_id="writer",
        content="",
        status="complete",
        tool_calls=[
            {
                "id": "call_write",
                "name": "write_chapter",
                "args": {"title": "第一章"},
            }
        ],
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content='{"type":"preview","success":true,"reason":"approval_preview","chapter":{"title":"第一章"},"metadata":{"chapter_diff":{"operation":"create","sections":[]}}}',
        status="aborted",
        tool_call_id="call_write",
        tool_name="write_chapter",
    )

    messages = await load_task_messages_for_agent_session(db_session, sid)

    tool_messages = [message for message in messages if message.message_type == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0].message_status == "completed"
    assert tool_messages[0].payload["tool_result"]["reason"] == "approval_preview"
    assert tool_messages[0].payload["tool_result"]["data"]["metadata"]["chapter_diff"]["operation"] == "create"


@pytest.mark.asyncio
async def test_projects_completed_write_tool_result_keeps_chapter_diff_for_reload(
    db_session: AsyncSession,
    sample_task,
) -> None:
    sid = "session_completed_write_tool_projection"

    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        agent_id="writer",
        content="",
        status="complete",
        tool_calls=[
            {
                "id": "call_write",
                "name": "write_chapter",
                "args": {"title": "第一章", "content": "正文"},
            }
        ],
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content='{"type":"ok","success":true,"tool_name":"write_chapter","message":"章节已写入","word_count":2,"chapter":{"id":"chapter_1","title":"第一章","content":"正文","order":1},"metadata":{"chapter_diff":{"operation":"create","chapter_id":"chapter_1","chapter_title":"第一章","order":1,"sections":[{"type":"content","lines":[{"type":"added","before_line_number":null,"after_line_number":1,"text":"正文"}]}]}},"affected_chapters":["chapter_1"]}',
        status="complete",
        tool_call_id="call_write",
        tool_name="write_chapter",
    )

    messages = await load_task_messages_for_agent_session(db_session, sid)

    tool_messages = [message for message in messages if message.message_type == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0].payload["tool_result"]["data"]["word_count"] == 2
    assert tool_messages[0].payload["tool_result"]["data"]["chapter"]["id"] == "chapter_1"
    assert tool_messages[0].payload["tool_result"]["data"]["metadata"]["chapter_diff"]["operation"] == "create"
    assert tool_messages[0].payload["tool_result"]["data"]["metadata"]["chapter_diff"]["chapter_id"] == "chapter_1"
    assert tool_messages[0].payload["tool_result"]["data"]["metadata"]["chapter_diff"]["sections"][0]["type"] == "content"
