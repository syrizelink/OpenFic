"""History-based continuation of an interrupted user turn."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence.child_runs import list_active_child_runs
from app.agent_runtime.persistence.model import AgentRunMessage
from app.agent_runtime.revisions import begin_user_revision
from app.agent_runtime.runner import checkpointer
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.core.errors import NotFoundError
from app.storage.models.revision import Revision
from app.storage.models.task import Task
from app.storage.services import task_service

RESUMPTION_PROMPT = (
    "[TASK RESUMPTION] Resume the interrupted task using the existing conversation. "
    "Check the current state before retrying interrupted tools. "
    "Do not repeat work that already completed."
)


class SessionNotContinuableError(Exception):
    pass


async def continuation_target(
    session: AsyncSession,
    session_id: str,
) -> tuple[Task, Revision, AgentRunMessage] | None:
    try:
        task = await task_service.get_task_by_agent_session_id(session, session_id)
    except NotFoundError:
        return None
    if task.is_running or await get_agent_run_registry().is_running(session_id):
        return None
    revision = (
        await session.get(Revision, task.current_revision_id)
        if task.current_revision_id
        else None
    )
    if (
        revision is None
        or revision.status not in {"cancelled", "failed", "interrupted"}
        or revision.revision_type != "agent"
        or revision.agent_session_id != session_id
        or revision.task_id != task.id
        or revision.project_id != task.project_id
    ):
        return None
    user = (
        await session.execute(
            select(AgentRunMessage)
            .where(
                col(AgentRunMessage.session_id) == session_id,
                col(AgentRunMessage.role) == "user",
            )
            .order_by(col(AgentRunMessage.seq).desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if (
        user is None
        or user.status != "sent"
        or user.task_id != task.id
        or user.project_id != task.project_id
        or revision.user_message_id != user.id
        or revision.user_message_seq != user.seq
    ):
        return None
    if revision.status != "cancelled":
        saver = await checkpointer.get_checkpointer()
        checkpoint = await saver.aget_tuple({"configurable": {"thread_id": session_id}})
        if checkpoint is not None:
            values = checkpoint.checkpoint.get("channel_values", {})
            if values.get("current_revision_id") == revision.id and any(
                len(write) >= 3 and write[1] == "__interrupt__" and write[2]
                for write in checkpoint.pending_writes or []
            ):
                return None
        if any(
            child.pending_approval_json
            for child in await list_active_child_runs(
                session,
                parent_session_id=session_id,
            )
        ):
            return None
    return task, revision, user


async def claim_continuation(
    session: AsyncSession,
    session_id: str,
) -> tuple[Revision, AgentRunMessage]:
    target = await continuation_target(session, session_id)
    if target is None:
        raise SessionNotContinuableError
    task, previous, user = target
    # Keep the old revision terminal. The task row is the cross-worker launch claim.
    claimed = (
        await session.execute(
            update(Task)
            .where(
                col(Task.id) == task.id,
                col(Task.current_revision_id) == previous.id,
                col(Task.is_running).is_(False),
                select(col(Revision.id))
                .where(
                    col(Revision.id) == previous.id,
                    col(Revision.status) == previous.status,
                )
                .exists(),
            )
            .values(is_running=True)
            .returning(col(Task.id))
        )
    ).scalar_one_or_none()
    if claimed is None:
        await session.rollback()
        raise SessionNotContinuableError
    try:
        saver = await checkpointer.get_checkpointer()
        checkpoint = await saver.aget_tuple({"configurable": {"thread_id": session_id}})
        checkpoint_id = (
            checkpoint.config.get("configurable", {}).get("checkpoint_id")
            if checkpoint is not None
            else None
        )
        revision = await begin_user_revision(
            session,
            project_id=task.project_id,
            task_id=task.id,
            agent_session_id=session_id,
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="继续未完成任务",
            pre_run_checkpoint_id=checkpoint_id,
            graph_thread_id=session_id,
            update_user_metadata=False,
        )
        revision.parent_revision_id = previous.id
        session.add(revision)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return revision, user
