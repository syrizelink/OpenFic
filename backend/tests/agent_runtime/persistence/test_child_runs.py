import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence.child_runs import (
    complete_child_run_request,
    create_child_run,
    enqueue_child_run_request,
    get_child_run_by_pending_approval,
    get_waiting_child_run_for_tool_call,
    list_child_runs_for_parent,
    record_child_run_pending_approval,
    rollback_child_runs_for_parent_revisions,
    update_child_run_status,
)
from app.agent_runtime.persistence.loader import load_history
from app.agent_runtime.persistence.model import (
    AgentChildRun,
    AgentChildRunRequest,
    AgentRunMessage,
)
from app.agent_runtime.persistence.task_projection import (
    load_task_messages_for_agent_session,
)


@pytest.mark.asyncio
async def test_create_child_run_persists_parent_and_child_thread_boundary(
    db_session: AsyncSession, sample_task
):
    row = await create_child_run(
        db_session,
        parent_session_id="parent-session",
        parent_task_id=sample_task.id,
        parent_thread_id="parent-thread",
        child_thread_id="child-thread",
        agent_key="writer",
        dispatch_id="dispatch-1",
        tool_call_id="tool-call-1",
        request={"goal": "write the scene"},
        metadata={"batch": 1},
    )

    assert row.status == "queued"
    assert row.request_json == {"goal": "write the scene"}
    assert row.metadata_json["batch"] == 1
    assert row.metadata_json["agent_number"].startswith("#")

    persisted = await db_session.get(AgentChildRun, row.id)
    assert persisted is not None
    assert persisted.parent_session_id == "parent-session"
    assert persisted.child_thread_id == "child-thread"


@pytest.mark.asyncio
async def test_update_child_run_status_records_completion_payload(
    db_session: AsyncSession, sample_task
):
    row = await create_child_run(
        db_session,
        parent_session_id="parent-session",
        parent_task_id=sample_task.id,
        parent_thread_id="parent-thread",
        child_thread_id="child-thread",
        agent_key="reviewer",
        dispatch_id="dispatch-1",
        tool_call_id="tool-call-1",
        request={"goal": "review the scene"},
    )

    updated = await update_child_run_status(
        db_session,
        row.id,
        "completed",
        result={"status": "approved"},
    )

    assert updated.status == "completed"
    assert updated.result_json == {"status": "approved"}
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_child_run_pending_approval_maps_to_child_thread_and_clears_on_terminal(
    db_session: AsyncSession,
    sample_task,
):
    row = await create_child_run(
        db_session,
        parent_session_id="parent-session",
        parent_task_id=sample_task.id,
        parent_thread_id="parent-thread",
        child_thread_id="child-thread",
        agent_key="writer",
        dispatch_id="dispatch-1",
        tool_call_id="tool-call-1",
        request={},
    )

    await record_child_run_pending_approval(
        db_session,
        row.id,
        approval_id="approval-1",
        approval_request={"type": "tool_approval", "approval_id": "approval-1"},
    )

    by_approval = await get_child_run_by_pending_approval(
        db_session,
        parent_session_id="parent-session",
        approval_id="approval-1",
    )
    by_tool_call = await get_waiting_child_run_for_tool_call(
        db_session,
        parent_session_id="parent-session",
        tool_call_id="tool-call-1",
    )

    assert by_approval is not None
    assert by_approval.id == row.id
    assert by_approval.child_thread_id == "child-thread"
    assert by_tool_call is not None
    assert by_tool_call.id == row.id

    await update_child_run_status(db_session, row.id, "completed", result={"ok": True})
    assert (
        await get_child_run_by_pending_approval(
            db_session,
            parent_session_id="parent-session",
            approval_id="approval-1",
        )
        is None
    )


@pytest.mark.asyncio
async def test_list_child_runs_for_parent_orders_by_creation(
    db_session: AsyncSession, sample_task
):
    await create_child_run(
        db_session,
        parent_session_id="parent-session",
        parent_task_id=sample_task.id,
        parent_thread_id="parent-thread",
        child_thread_id="child-1",
        agent_key="composer",
        dispatch_id="dispatch-1",
        tool_call_id="tool-call-1",
        request={},
    )
    await create_child_run(
        db_session,
        parent_session_id="parent-session",
        parent_task_id=sample_task.id,
        parent_thread_id="parent-thread",
        child_thread_id="child-2",
        agent_key="writer",
        dispatch_id="dispatch-2",
        tool_call_id="tool-call-2",
        request={},
    )

    rows = await list_child_runs_for_parent(db_session, "parent-session")

    assert [row.child_thread_id for row in rows] == ["child-1", "child-2"]


@pytest.mark.asyncio
async def test_rollback_child_runs_restores_notify_request_to_previous_completed_state(
    db_session: AsyncSession,
    sample_task,
):
    row = await create_child_run(
        db_session,
        parent_session_id="parent-session",
        parent_task_id=sample_task.id,
        parent_thread_id="parent-thread",
        child_thread_id="child-thread",
        agent_key="writer",
        dispatch_id="dispatch-1",
        tool_call_id="tool-call-1",
        request={},
        parent_revision_id="rev-1",
        child_user_message_id="child-user-1",
        child_user_message_seq=0,
        pre_request_checkpoint_id="cp-before-dispatch",
    )
    request_result = await db_session.execute(
        select(AgentChildRunRequest).where(
            col(AgentChildRunRequest.child_run_id) == row.id,
            col(AgentChildRunRequest.seq) == 0,
        )
    )
    first_request = request_result.scalar_one()

    db_session.add_all(
        [
            AgentRunMessage(
                session_id="child-thread",
                task_id=sample_task.id,
                project_id=sample_task.project_id,
                role="user",
                content="第一轮任务",
                status="sent",
                message_type="user_request",
                seq=0,
            ),
            AgentRunMessage(
                session_id="child-thread",
                task_id=sample_task.id,
                project_id=sample_task.project_id,
                role="assistant",
                content="第一轮结果",
                status="complete",
                seq=1,
            ),
        ]
    )
    await complete_child_run_request(
        db_session,
        first_request.id,
        assistant_content="第一轮结果",
    )

    notify_request = await enqueue_child_run_request(
        db_session,
        child_run_id=row.id,
        request_kind="notify",
        content="第二轮任务",
        parent_revision_id="rev-2",
        child_user_message_id="child-user-2",
        child_user_message_seq=2,
        pre_request_checkpoint_id="cp-before-notify",
    )
    db_session.add_all(
        [
            AgentRunMessage(
                session_id="child-thread",
                task_id=sample_task.id,
                project_id=sample_task.project_id,
                role="user",
                content="第二轮任务",
                status="sent",
                message_type="user_request",
                seq=2,
            ),
            AgentRunMessage(
                session_id="child-thread",
                task_id=sample_task.id,
                project_id=sample_task.project_id,
                role="assistant",
                content="第二轮结果",
                status="complete",
                seq=3,
            ),
        ]
    )
    await complete_child_run_request(
        db_session,
        notify_request.id,
        assistant_content="第二轮结果",
    )

    rollback_result = await rollback_child_runs_for_parent_revisions(
        db_session,
        parent_revision_ids=["rev-2"],
    )

    restored = await db_session.get(AgentChildRun, row.id)
    rolled_back_request = await db_session.get(AgentChildRunRequest, notify_request.id)
    message_result = await db_session.execute(
        select(AgentRunMessage)
        .where(col(AgentRunMessage.session_id) == "child-thread")
        .order_by(col(AgentRunMessage.seq).asc())
    )
    messages = list(message_result.scalars().all())

    assert rollback_result.checkpoint_boundaries == [("child-thread", "cp-before-notify")]
    assert rollback_result.child_run_ids == [row.id]
    assert restored is not None
    assert restored.is_active is True
    assert restored.status == "completed"
    assert restored.last_assistant_content == "第一轮结果"
    assert rolled_back_request is not None
    assert rolled_back_request.status == "cancelled"
    assert [message.content for message in messages] == ["第一轮任务", "第一轮结果"]

@pytest.mark.asyncio
async def test_hidden_system_reminder_remains_visible_to_llm_history(
    db_session: AsyncSession, sample_task
):
    db_session.add(
        AgentRunMessage(
            session_id="session-reminder",
            task_id=sample_task.id,
            project_id=sample_task.project_id,
            role="user",
            content="<system-reminder>writer child run completed</system-reminder>",
            status="sent",
            message_type="message",
            display_channel="hidden",
            llm_visibility="visible",
            seq=0,
        )
    )
    await db_session.commit()

    messages = await load_history(db_session, "session-reminder")

    assert [message.content for message in messages] == [
        "<system-reminder>writer child run completed</system-reminder>"
    ]


@pytest.mark.asyncio
async def test_hidden_system_reminder_stays_hidden_in_task_projection(
    db_session: AsyncSession, sample_task
):
    db_session.add(
        AgentRunMessage(
            session_id="session-reminder-projection",
            task_id=sample_task.id,
            project_id=sample_task.project_id,
            role="user",
            content="<system-reminder>reviewer child run completed</system-reminder>",
            status="sent",
            message_type="message",
            display_channel="hidden",
            llm_visibility="visible",
            seq=0,
        )
    )
    await db_session.commit()

    messages = await load_task_messages_for_agent_session(
        db_session,
        "session-reminder-projection",
    )

    assert len(messages) == 1
    assert messages[0].display_channel == "hidden"
    assert messages[0].content == (
        "<system-reminder>reviewer child run completed</system-reminder>"
    )
