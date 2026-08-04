from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence.model import (
    AgentAttachment,
    AgentChildRun,
    AgentChildRunRequest,
    AgentContextCompaction,
    AgentRunMessage,
    PlanRecord,
    PlanTodoRecord,
)
from app.storage.models.llm_audit_log import LLMAuditLog
from app.storage.models.task_message import TaskMessage
from app.storage.services import task_service


async def test_cleanup_orphaned_task_data_keeps_audit_logs(
    session: AsyncSession,
) -> None:
    session.add_all(
        [
            AgentAttachment(
                id="orphan-attachment",
                session_id="orphan-session",
                task_id="missing-task",
                project_id="project",
                storage_name="orphan-session/orphan-attachment.png",
                file_name="orphan.png",
                mime_type="image/png",
                size_bytes=1,
                width=1,
                height=1,
            ),
            TaskMessage(
                id="orphan-task-message",
                task_id="missing-task",
                role="assistant",
                content="orphan task message",
                tool_calls="[]",
                message_metadata="{}",
            ),
            AgentRunMessage(
                id="orphan-message",
                session_id="orphan-session",
                task_id="missing-task",
                project_id="project",
                role="assistant",
                status="completed",
                seq=0,
            ),
            AgentChildRun(
                id="orphan-child",
                parent_session_id="orphan-session",
                parent_task_id="missing-task",
                parent_thread_id="orphan-session",
                child_thread_id="orphan-child-thread",
                agent_key="writer",
                dispatch_id="writer",
                tool_call_id="tool-writer",
            ),
            AgentChildRunRequest(
                id="orphan-request",
                child_run_id="orphan-child",
                parent_session_id="orphan-session",
                parent_task_id="missing-task",
                request_kind="dispatch",
                seq=0,
            ),
            AgentContextCompaction(
                id="orphan-compaction",
                session_id="orphan-session",
                task_id="missing-task",
                project_id="project",
                start_seq=0,
                end_seq=1,
                summary="orphan summary",
                trigger="manual",
            ),
            PlanRecord(id="orphan-plan", session_id="orphan-session"),
            PlanTodoRecord(
                id="orphan-todo",
                plan_id="orphan-plan",
                content="orphan todo",
                sort_index=0,
            ),
            PlanRecord(id="plan-only-orphan", session_id="plan-only-session"),
            PlanTodoRecord(
                id="plan-only-orphan-todo",
                plan_id="plan-only-orphan",
                content="orphan-only todo",
                sort_index=0,
            ),
            LLMAuditLog(
                id="orphan-audit",
                task_id="missing-task",
                session_id="orphan-session",
                project_id="project",
                operation="build",
                model_id="test-model",
                status="success",
            ),
        ]
    )
    await session.commit()

    deleted_rows = await task_service.cleanup_orphaned_task_data(session)

    assert deleted_rows == 10
    for model in (
        AgentAttachment,
        TaskMessage,
        AgentRunMessage,
        AgentChildRun,
        AgentChildRunRequest,
        AgentContextCompaction,
        PlanRecord,
        PlanTodoRecord,
    ):
        result = await session.execute(select(model))
        assert result.scalars().all() == []
    audit_result = await session.execute(
        select(LLMAuditLog).where(LLMAuditLog.id == "orphan-audit")
    )
    assert audit_result.scalar_one_or_none() is not None
