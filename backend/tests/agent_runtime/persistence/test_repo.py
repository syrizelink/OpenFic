"""Repo 测试。"""

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import repo
from app.agent_runtime.persistence.errors import PersistenceWriteError
from app.agent_runtime.persistence.model import AgentRunMessage


@pytest.mark.asyncio
async def test_next_seq_starts_at_zero(db_session: AsyncSession, sample_task):
    seq = await repo.next_seq(db_session, "session_a")
    assert seq == 0


@pytest.mark.asyncio
async def test_next_seq_increments(db_session: AsyncSession, sample_task):
    await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="hi",
        status="pending",
    )
    seq = await repo.next_seq(db_session, "session_a")
    assert seq == 1


@pytest.mark.asyncio
async def test_next_seq_isolated_per_session(db_session: AsyncSession, sample_task):
    await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="hi",
        status="pending",
    )
    seq_b = await repo.next_seq(db_session, "session_b")
    assert seq_b == 0


@pytest.mark.asyncio
async def test_insert_message_assigns_seq_and_persists(
    db_session: AsyncSession, sample_task
):
    msg = await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="hello",
        status="complete",
        agent_id="writer",
        tool_calls=[{"id": "call_1", "name": "read_chapter", "args": {}}],
        metadata={"iteration": 0},
    )
    assert msg.seq == 0
    assert msg.role == "assistant"
    assert msg.message_type == "message"
    assert msg.display_channel == "list"
    assert msg.tool_calls == [{"id": "call_1", "name": "read_chapter", "args": {}}]
    assert msg.metadata == {"iteration": 0}

    row = await db_session.get(AgentRunMessage, msg.id)
    assert row is not None
    assert row.tool_calls == json.dumps(
        [{"id": "call_1", "name": "read_chapter", "args": {}}]
    )


@pytest.mark.asyncio
async def test_insert_message_persists_message_type_and_display_channel(
    db_session: AsyncSession, sample_task
):
    msg = await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="system",
        status="complete",
        message_type="node_start",
        display_channel="hidden",
        metadata={"node": "composer"},
    )

    assert msg.message_type == "node_start"
    assert msg.display_channel == "hidden"
    row = await db_session.get(AgentRunMessage, msg.id)
    assert row is not None
    assert row.message_type == "node_start"
    assert row.display_channel == "hidden"


@pytest.mark.asyncio
async def test_list_by_session_orders_by_seq(db_session: AsyncSession, sample_task):
    for i in range(3):
        await repo.insert_message(
            db_session,
            session_id="session_a",
            task_id=sample_task.id,
            project_id=sample_task.project_id,
            role="user",
            content=f"msg-{i}",
            status="complete",
        )

    items = await repo.list_by_session(db_session, "session_a")
    assert [m.content for m in items] == ["msg-0", "msg-1", "msg-2"]
    assert [m.seq for m in items] == [0, 1, 2]


@pytest.mark.asyncio
async def test_list_by_session_filters_by_session(db_session: AsyncSession, sample_task):
    await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="a",
        status="complete",
    )
    await repo.insert_message(
        db_session,
        session_id="session_b",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="b",
        status="complete",
    )
    items = await repo.list_by_session(db_session, "session_a")
    assert len(items) == 1
    assert items[0].content == "a"


@pytest.mark.asyncio
async def test_delete_from_seq_includes_anchor(db_session: AsyncSession, sample_task):
    for i in range(5):
        await repo.insert_message(
            db_session,
            session_id="session_a",
            task_id=sample_task.id,
            project_id=sample_task.project_id,
            role="user",
            content=f"msg-{i}",
            status="complete",
        )

    deleted = await repo.delete_from_seq(db_session, "session_a", 2)
    assert deleted == 3
    remaining = await repo.list_by_session(db_session, "session_a")
    assert [m.seq for m in remaining] == [0, 1]


@pytest.mark.asyncio
async def test_delete_pending_by_session(db_session: AsyncSession, sample_task):
    await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="pending-msg",
        status="pending",
    )
    await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="sent-msg",
        status="sent",
    )

    deleted = await repo.delete_pending_by_session(db_session, "session_a")
    assert deleted == 1
    items = await repo.list_by_session(db_session, "session_a")
    assert [m.content for m in items] == ["sent-msg"]


@pytest.mark.asyncio
async def test_delete_pending_by_session_keeps_assistant_pending(
    db_session: AsyncSession, sample_task
):
    """role 过滤：assistant pending 不应被这条 user-only 清理路径删除。"""
    await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="user-pending",
        status="pending",
    )
    await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="assistant",
        content="assistant-pending",
        status="pending",
    )
    await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="user-complete",
        status="complete",
    )

    deleted = await repo.delete_pending_by_session(db_session, "session_a")
    assert deleted == 1
    items = await repo.list_by_session(db_session, "session_a")
    assert {m.content for m in items} == {"assistant-pending", "user-complete"}


@pytest.mark.asyncio
async def test_update_status(db_session: AsyncSession, sample_task):
    msg = await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="hi",
        status="pending",
    )
    await repo.update_status(db_session, msg.id, "sent")
    items = await repo.list_by_session(db_session, "session_a")
    assert items[0].status == "sent"


@pytest.mark.asyncio
async def test_update_status_missing_raises_write_error(
    db_session: AsyncSession, sample_task
):
    with pytest.raises(PersistenceWriteError):
        await repo.update_status(db_session, "msg_does_not_exist", "sent")


@pytest.mark.asyncio
async def test_delete_by_id(db_session: AsyncSession, sample_task):
    msg = await repo.insert_message(
        db_session,
        session_id="session_a",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        role="user",
        content="hi",
        status="pending",
    )
    deleted = await repo.delete_by_id(db_session, msg.id)
    assert deleted is True
    items = await repo.list_by_session(db_session, "session_a")
    assert items == []


@pytest.mark.asyncio
async def test_delete_by_id_missing_returns_false(
    db_session: AsyncSession, sample_task
):
    deleted = await repo.delete_by_id(db_session, "msg_does_not_exist")
    assert deleted is False
