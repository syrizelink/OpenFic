"""load_history 测试。"""

import json
from pathlib import Path

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import repo
from app.agent_runtime.attachments import (
    build_image_content_blocks,
    cleanup_orphaned_agent_attachment_files,
    copy_attachments_for_fork,
    delete_attachments_for_task,
)
from app.agent_runtime.persistence.model import AgentAttachment
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
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        content="sys",
        status="complete",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="hi",
        status="sent",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="hello back",
        status="complete",
    )

    msgs = await load_history(db_session, sid)
    assert len(msgs) == 3
    assert isinstance(msgs[0], SystemMessage) and msgs[0].content == "sys"
    assert isinstance(msgs[1], HumanMessage) and msgs[1].content == "hi"
    assert isinstance(msgs[2], AIMessage) and msgs[2].content == "hello back"


@pytest.mark.asyncio
async def test_load_history_preserves_user_attachment_metadata(
    db_session: AsyncSession,
    sample_task,
) -> None:
    await repo.insert_message(
        db_session,
        session_id="session-with-image",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="请看附件",
        status="sent",
        metadata={
            "attachments": [
                {
                    "id": "attachment-1",
                    "storage_name": "session-with-image/attachment-1.png",
                    "mime_type": "image/png",
                }
            ]
        },
    )

    messages = await load_history(db_session, "session-with-image")

    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "请看附件"
    assert messages[0].additional_kwargs["openfic_attachments"] == [
        {
            "id": "attachment-1",
            "storage_name": "session-with-image/attachment-1.png",
            "mime_type": "image/png",
        }
    ]


@pytest.mark.asyncio
async def test_build_image_content_blocks_reads_server_attachment_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "agent_attachments_dir", tmp_path)
    attachment_path = tmp_path / "session-1" / "reference.png"
    attachment_path.parent.mkdir()
    attachment_path.write_bytes(b"image-data")

    blocks = await build_image_content_blocks(
        [
            {
                "storage_name": "session-1/reference.png",
                "mime_type": "image/png",
            }
        ]
    )

    assert blocks == [
        {"type": "image", "base64": "aW1hZ2UtZGF0YQ==", "mime_type": "image/png"}
    ]


@pytest.mark.asyncio
async def test_copy_attachments_for_fork_creates_session_owned_copy(
    db_session: AsyncSession,
    sample_task,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "agent_attachments_dir", tmp_path)
    (tmp_path / "source" / "image.png").parent.mkdir()
    (tmp_path / "source" / "image.png").write_bytes(b"source-image")
    db_session.add(
        AgentAttachment(
            id="source-image",
            session_id="source",
            task_id=sample_task.id,
            project_id=sample_task.project_id,
            storage_name="source/image.png",
            file_name="image.png",
            mime_type="image/png",
            size_bytes=12,
            width=2,
            height=3,
        )
    )
    await db_session.commit()

    copied = await copy_attachments_for_fork(
        db_session,
        source_session_id="source",
        target_session_id="fork",
        target_task_id=sample_task.id,
        project_id=sample_task.project_id,
        attachment_ids={"source-image"},
    )

    assert copied["source-image"]["id"] != "source-image"
    assert copied["source-image"]["storage_name"].startswith("fork/")
    assert (tmp_path / copied["source-image"]["storage_name"]).read_bytes() == b"source-image"


@pytest.mark.asyncio
async def test_delete_attachments_for_task_removes_files_and_records(
    db_session: AsyncSession,
    sample_task,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "agent_attachments_dir", tmp_path)
    storage_name = "session-1/image.png"
    path = tmp_path / storage_name
    path.parent.mkdir()
    path.write_bytes(b"image-data")
    db_session.add(
        AgentAttachment(
            id="attachment-1",
            session_id="session-1",
            task_id=sample_task.id,
            project_id=sample_task.project_id,
            storage_name=storage_name,
            file_name="image.png",
            mime_type="image/png",
            size_bytes=10,
            width=2,
            height=3,
        )
    )
    await db_session.commit()

    deleted = await delete_attachments_for_task(db_session, task_id=sample_task.id)
    await db_session.commit()

    assert deleted >= 1
    assert not path.exists()
    assert not path.parent.exists()
    assert await db_session.get(AgentAttachment, "attachment-1") is None


@pytest.mark.asyncio
async def test_cleanup_orphaned_agent_attachment_files_keeps_recorded_files(
    db_session: AsyncSession,
    sample_task,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "agent_attachments_dir", tmp_path)
    session_id = sample_task.agent_session_id or "session_test"
    kept_path = tmp_path / session_id / "kept.png"
    orphan_path = tmp_path / "orphan-session" / "orphan.png"
    kept_path.parent.mkdir()
    orphan_path.parent.mkdir()
    kept_path.write_bytes(b"kept")
    orphan_path.write_bytes(b"orphan")
    db_session.add(
        AgentAttachment(
            id="attachment-kept",
            session_id=session_id,
            task_id=sample_task.id,
            project_id=sample_task.project_id,
            storage_name=f"{session_id}/kept.png",
            file_name="kept.png",
            mime_type="image/png",
            size_bytes=4,
            width=2,
            height=3,
        )
    )
    await db_session.commit()

    deleted = await cleanup_orphaned_agent_attachment_files(db_session)

    assert deleted >= 1
    assert kept_path.exists()
    assert not orphan_path.exists()
    assert not orphan_path.parent.exists()


@pytest.mark.asyncio
async def test_cleanup_orphaned_agent_attachment_files_removes_empty_deleted_session_directory(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.settings import settings

    monkeypatch.setattr(settings, "agent_attachments_dir", tmp_path)
    deleted_session_dir = tmp_path / "deleted-session"
    deleted_session_dir.mkdir()

    await cleanup_orphaned_agent_attachment_files(db_session)

    assert not deleted_session_dir.exists()


@pytest.mark.asyncio
async def test_load_history_skips_pending_user(db_session: AsyncSession, sample_task):
    sid = "session_a"
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="sent-1",
        status="sent",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="pending-1",
        status="pending",
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
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="",
        status="complete",
        tool_calls=[{"id": "c1", "name": "read_chapter", "args": {"order": 1}}],
    )
    await repo.insert_message(
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
            {
                "id": "call_2",
                "name": "dispatch_subagent",
                "args": {"agent": "reviewer"},
            },
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
async def test_load_history_drops_orphan_tool(db_session: AsyncSession, sample_task):
    sid = "session_a"
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="hi",
        status="sent",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content="orphan",
        status="complete",
        tool_call_id="missing",
        tool_name="x",
    )
    msgs = await load_history(db_session, sid)
    assert len(msgs) == 1
    assert isinstance(msgs[0], HumanMessage)


@pytest.mark.asyncio
async def test_load_history_drops_tool_response_separated_from_its_call(
    db_session: AsyncSession,
    sample_task,
) -> None:
    sid = "session_separated_tool_response"
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="calling",
        status="complete",
        tool_calls=[{"id": "call_1", "name": "edit_note", "args": {}}],
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="intervening response",
        status="complete",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content="late result",
        status="complete",
        tool_call_id="call_1",
        tool_name="edit_note",
    )

    messages = await load_history(db_session, sid)

    assert len(messages) == 1
    assert isinstance(messages[0], AIMessage)
    assert messages[0].content == "intervening response"


@pytest.mark.asyncio
async def test_load_history_strips_unmatched_assistant_tool_calls(
    db_session: AsyncSession, sample_task
):
    sid = "session_a"
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="text",
        status="complete",
        tool_calls=[
            {"id": "ok", "name": "n", "args": {}},
            {"id": "missing", "name": "n", "args": {}},
        ],
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content="ok-result",
        status="complete",
        tool_call_id="ok",
        tool_name="n",
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
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="first",
        reasoning="thinking-1",
        status="complete",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="second",
        reasoning="thinking-2",
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
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="half",
        status="partial",
        tool_calls=[{"id": "c1", "name": "n", "args": {}}],
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content="[中断] 工具未执行",
        status="aborted",
        tool_call_id="c1",
        tool_name="n",
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
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="calling",
        status="complete",
        tool_calls=[{"id": "c1", "name": "n", "args": {}}],
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content="[中断] 工具未执行",
        status="aborted",
        tool_call_id="c1",
        tool_name="n",
    )
    await repo.insert_message(
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="tool",
        content="ok-result",
        status="complete",
        tool_call_id="c1",
        tool_name="n",
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
        db_session,
        session_id=sid,
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="",
        status="complete",
        tool_calls=[
            {
                "id": "c1",
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
