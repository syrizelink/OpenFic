"""load_history 测试。"""

import json

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import repo
from app.agent_runtime.persistence.loader import load_history


@pytest.mark.asyncio
async def test_load_history_empty_session(db_session: AsyncSession, sample_task):
    msgs = await load_history(db_session, "empty_session")
    assert msgs == []


@pytest.mark.asyncio
async def test_load_history_basic_roles_in_seq_order(
    db_session: AsyncSession, sample_task
):
    sid = "session_a"
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system", content="sys", status="complete",
    )
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user", content="hi", status="sent",
    )
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant", content="hello back", status="complete",
    )

    msgs = await load_history(db_session, sid)
    assert len(msgs) == 3
    assert isinstance(msgs[0], SystemMessage) and msgs[0].content == "sys"
    assert isinstance(msgs[1], HumanMessage) and msgs[1].content == "hi"
    assert isinstance(msgs[2], AIMessage) and msgs[2].content == "hello back"


@pytest.mark.asyncio
async def test_load_history_skips_pending_user(
    db_session: AsyncSession, sample_task
):
    sid = "session_a"
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user", content="sent-1", status="sent",
    )
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user", content="pending-1", status="pending",
    )
    msgs = await load_history(db_session, sid)
    assert [m.content for m in msgs] == ["sent-1"]


@pytest.mark.asyncio
async def test_load_history_skips_hidden_node_events(
    db_session: AsyncSession, sample_task
):
    sid = "session_a"
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        message_type="node_start",
        display_channel="hidden",
        metadata={"node": "composer", "phase": "start", "node_status": "running"},
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="sent-1",
        status="sent",
    )

    msgs = await load_history(db_session, sid)

    assert len(msgs) == 1
    assert isinstance(msgs[0], HumanMessage)
    assert msgs[0].content == "sent-1"


@pytest.mark.asyncio
async def test_load_history_skips_display_only_compaction_marker(
    db_session: AsyncSession,
    sample_task,
) -> None:
    sid = "session_display_only_compaction"
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="压缩前消息",
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
        metadata={"kind": "compaction", "compaction_id": "cmp_1"},
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="压缩后回复",
        status="complete",
    )

    msgs = await load_history(db_session, sid)

    assert [message.content for message in msgs] == ["压缩前消息", "压缩后回复"]
    assert all(message.content != "已进行压缩" for message in msgs)


@pytest.mark.asyncio
async def test_load_history_pairs_assistant_with_tool(
    db_session: AsyncSession, sample_task
):
    sid = "session_a"
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant", content="", status="complete",
        tool_calls=[{"id": "c1", "name": "read_chapter", "args": {"order": 1}}],
    )
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool", content="chapter body", status="complete",
        tool_call_id="c1", tool_name="read_chapter",
    )
    msgs = await load_history(db_session, sid)
    assert len(msgs) == 2
    assert isinstance(msgs[0], AIMessage)
    assert len(msgs[0].tool_calls) == 1
    tc0 = msgs[0].tool_calls[0]
    assert tc0["id"] == "c1"
    assert tc0["name"] == "read_chapter"
    assert tc0["args"] == {"order": 1}
    assert isinstance(msgs[1], ToolMessage)
    assert msgs[1].tool_call_id == "c1"


@pytest.mark.asyncio
async def test_load_history_orders_tool_results_by_assistant_tool_call_order(
    db_session: AsyncSession,
    sample_task,
) -> None:
    sid = "session_parallel_tools"
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="",
        status="complete",
        tool_calls=[
            {"id": "call_1", "name": "dispatch_subagent", "args": {"agent": "writer"}},
            {"id": "call_2", "name": "dispatch_subagent", "args": {"agent": "reviewer"}},
        ],
    )
    # 并行工具按实际完成顺序入库：call_2 比 call_1 先完成。
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content="review complete",
        status="complete",
        tool_call_id="call_2",
        tool_name="dispatch_subagent",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content="draft complete",
        status="complete",
        tool_call_id="call_1",
        tool_name="dispatch_subagent",
    )

    messages = await load_history(db_session, sid)

    assert isinstance(messages[0], AIMessage)
    assert [
        message.tool_call_id
        for message in messages[1:]
        if isinstance(message, ToolMessage)
    ] == ["call_1", "call_2"]


@pytest.mark.asyncio
async def test_load_history_adds_openfic_response_metadata_for_seq_and_tool_name(
    db_session: AsyncSession, sample_task
):
    sid = "session_response_metadata"
    user = await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="hi",
        status="sent",
    )
    assistant = await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="calling",
        status="complete",
        tool_calls=[{"id": "c1", "name": "read_chapter", "args": {}}],
    )
    tool = await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content="chapter body",
        status="complete",
        tool_call_id="c1",
        tool_name="read_chapter",
    )

    msgs = await load_history(db_session, sid)

    assert len(msgs) == 3
    assert isinstance(msgs[0], HumanMessage)
    assert msgs[0].response_metadata["openfic_seq"] == user.seq
    assert isinstance(msgs[1], AIMessage)
    assert msgs[1].response_metadata["openfic_seq"] == assistant.seq
    assert isinstance(msgs[2], ToolMessage)
    assert msgs[2].response_metadata["openfic_seq"] == tool.seq
    assert msgs[2].response_metadata["openfic_tool_name"] == "read_chapter"


@pytest.mark.asyncio
async def test_load_history_drops_orphan_tool(
    db_session: AsyncSession, sample_task
):
    sid = "session_a"
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user", content="hi", status="sent",
    )
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool", content="orphan", status="complete",
        tool_call_id="missing", tool_name="x",
    )
    msgs = await load_history(db_session, sid)
    assert len(msgs) == 1
    assert isinstance(msgs[0], HumanMessage)


@pytest.mark.asyncio
async def test_load_history_strips_unmatched_assistant_tool_calls(
    db_session: AsyncSession, sample_task
):
    sid = "session_a"
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant", content="text", status="complete",
        tool_calls=[
            {"id": "ok", "name": "n", "args": {}},
            {"id": "missing", "name": "n", "args": {}},
        ],
    )
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool", content="ok-result", status="complete",
        tool_call_id="ok", tool_name="n",
    )
    msgs = await load_history(db_session, sid)
    assert len(msgs) == 2
    assert isinstance(msgs[0], AIMessage)
    assert len(msgs[0].tool_calls) == 1
    tc0 = msgs[0].tool_calls[0]
    assert tc0["id"] == "ok"
    assert tc0["name"] == "n"
    assert tc0["args"] == {}


@pytest.mark.asyncio
async def test_load_history_reasoning_only_on_latest_assistant(
    db_session: AsyncSession, sample_task
):
    sid = "session_a"
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant", content="first", reasoning="thinking-1",
        status="complete",
    )
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant", content="second", reasoning="thinking-2",
        status="complete",
    )
    msgs = await load_history(db_session, sid)
    assert len(msgs) == 2
    assert "reasoning_content" not in msgs[0].additional_kwargs
    assert msgs[1].additional_kwargs["reasoning_content"] == "thinking-2"


@pytest.mark.asyncio
async def test_load_history_partial_assistant_and_aborted_tool_kept(
    db_session: AsyncSession, sample_task
):
    sid = "session_a"
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant", content="half", status="partial",
        tool_calls=[{"id": "c1", "name": "n", "args": {}}],
    )
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool", content="[中断] 工具未执行", status="aborted",
        tool_call_id="c1", tool_name="n",
    )
    msgs = await load_history(db_session, sid)
    assert len(msgs) == 2
    assert isinstance(msgs[0], AIMessage) and msgs[0].content == "half"
    assert len(msgs[0].tool_calls) == 1
    tc0 = msgs[0].tool_calls[0]
    assert tc0["id"] == "c1"
    assert tc0["name"] == "n"
    assert tc0["args"] == {}
    assert isinstance(msgs[1], ToolMessage)
    assert msgs[1].content == "[中断] 工具未执行"


@pytest.mark.asyncio
async def test_load_history_prefers_final_tool_result_over_aborted_placeholder(
    db_session: AsyncSession, sample_task
):
    sid = "session_a"
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant", content="calling", status="complete",
        tool_calls=[{"id": "c1", "name": "n", "args": {}}],
    )
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool", content="[中断] 工具未执行", status="aborted",
        tool_call_id="c1", tool_name="n",
    )
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool", content="ok-result", status="complete",
        tool_call_id="c1", tool_name="n",
    )

    msgs = await load_history(db_session, sid)

    assert len(msgs) == 2
    assert isinstance(msgs[0], AIMessage)
    assert len(msgs[0].tool_calls) == 1
    assert msgs[0].tool_calls[0]["id"] == "c1"
    assert isinstance(msgs[1], ToolMessage)
    assert msgs[1].tool_call_id == "c1"
    assert msgs[1].content == "ok-result"


@pytest.mark.asyncio
async def test_load_history_preserves_full_write_tool_result_payload(
    db_session: AsyncSession, sample_task
):
    sid = "session_write_tool_compaction"
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant", content="", status="complete",
        tool_calls=[{"id": "c1", "name": "write_chapter", "args": {"title": "第一章", "content": "正文"}}],
    )
    await repo.insert_message(
        db_session, session_id=sid, task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content=json.dumps(
            {
                "type": "ok",
                "success": True,
                "tool_name": "write_chapter",
                "revision_id": "rev-1",
                "word_count": 2,
                "chapter": {"id": "chap-1", "title": "第一章", "content": "正文"},
                "metadata": {"chapter_diff": {"operation": "create", "sections": []}},
                "affected_chapters": ["chap-1"],
                "message": "章节已写入",
            },
            ensure_ascii=False,
        ),
        status="complete",
        tool_call_id="c1",
        tool_name="write_chapter",
    )

    msgs = await load_history(db_session, sid)

    assert len(msgs) == 2
    assert isinstance(msgs[1], ToolMessage)
    assert msgs[1].tool_call_id == "c1"
    content = msgs[1].content
    assert isinstance(content, str)
    assert json.loads(content) == {
        "type": "ok",
        "success": True,
        "tool_name": "write_chapter",
        "revision_id": "rev-1",
        "word_count": 2,
        "chapter": {"id": "chap-1", "title": "第一章", "content": "正文"},
        "metadata": {"chapter_diff": {"operation": "create", "sections": []}},
        "affected_chapters": ["chap-1"],
        "message": "章节已写入",
    }
