"""Fork helpers for agent runtime sessions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence import compaction_repo, repo as message_repo
from app.agent_runtime.persistence.model import AgentRunMessage
from app.core.errors import NotFoundError
from app.core.ids import generate_id
from app.storage.models.revision import Revision
from app.storage.models.task import Task
from app.storage.repos import revision_repo, task_repo
from app.storage.services import task_service


@dataclass(frozen=True)
class AgentForkResult:
    session_id: str
    task: Task
    state_values: dict[str, Any]
    cloned_message_count: int


def _fork_title(title: str) -> str:
    suffix = "(Fork)"
    base = title or "Agent Session"
    return f"{base[: 200 - len(suffix)]}{suffix}"


def _new_session_id() -> str:
    return f"fork_{generate_id()}"


async def _list_revisions_through_seq(
    session: AsyncSession,
    *,
    agent_session_id: str,
    user_message_seq: int,
) -> list[Revision]:
    result = await session.execute(
        select(Revision)
        .where(col(Revision.agent_session_id) == agent_session_id)
        .where(col(Revision.revision_type) == "agent")
        .where(col(Revision.status) != "rolled_back")
        .where(col(Revision.user_message_seq) <= user_message_seq)
        .order_by(col(Revision.user_message_seq).asc(), col(Revision.created_at).asc())
    )
    return list(result.scalars().all())


def _build_fork_state(
    *,
    session_id: str,
    task: Task,
    model_config: dict[str, Any],
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "session_id": session_id,
        "task_id": task.id,
        "project_id": task.project_id,
        "model_config": model_config,
        "active_agent": None,
        "is_completed": True,
        "error": None,
        "retry_count": 0,
        "user_request": "",
        "installed_skill_ids": [],
        "current_revision_id": None,
    }
    return state


def _clone_message_row(
    row,
    *,
    session_id: str,
    task_id: str,
    seq: int,
) -> AgentRunMessage:
    metadata = dict(row.metadata or {})
    metadata.pop("revision_id", None)
    return AgentRunMessage(
        id=generate_id(),
        session_id=session_id,
        task_id=task_id,
        project_id=row.project_id,
        role=row.role,
        agent_id=row.agent_id,
        content=row.content,
        reasoning=row.reasoning,
        reasoning_duration_ms=row.reasoning_duration_ms,
        tool_calls=json.dumps(row.tool_calls, ensure_ascii=False) if row.tool_calls is not None else None,
        tool_call_id=row.tool_call_id,
        tool_name=row.tool_name,
        status=row.status,
        seq=seq,
        message_metadata=json.dumps(metadata, ensure_ascii=False),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def fork_agent_session_at_revision(
    session: AsyncSession,
    *,
    source_session_id: str,
    source_revision_id: str,
    model_config: dict[str, Any],
    new_session_id: str | None = None,
) -> AgentForkResult:
    target_revision = await revision_repo.get_by_id(session, source_revision_id)
    if target_revision is None:
        raise NotFoundError(f"版本不存在: {source_revision_id}")
    if target_revision.agent_session_id != source_session_id:
        raise NotFoundError(f"版本不属于会话: {source_revision_id}")
    if target_revision.status == "rolled_back":
        raise ValueError("已回滚的版本不能用于分叉")
    if target_revision.user_message_seq is None:
        raise ValueError("revision 缺少 user_message_seq，无法分叉")
    if not target_revision.task_id:
        raise ValueError("revision 缺少 task_id，无法分叉")

    source_task = await task_repo.get_by_id(session, target_revision.task_id)
    if source_task is None:
        raise NotFoundError(f"任务不存在: {target_revision.task_id}")

    rows = await message_repo.list_by_session(session, source_session_id)
    next_user_seq = min(
        (
            row.seq
            for row in rows
            if row.role == "user" and row.seq > target_revision.user_message_seq
        ),
        default=None,
    )
    rows_to_clone = [
        row
        for row in rows
        if next_user_seq is None or row.seq < next_user_seq
    ]
    seq_map = {row.seq: index for index, row in enumerate(rows_to_clone)}
    fork_session_id = new_session_id or _new_session_id()
    fork_task = await task_service.create_task(
        session=session,
        project_id=source_task.project_id,
        title=_fork_title(source_task.title),
        mode=cast(Literal["agent"], source_task.mode),
        agent_session_id=fork_session_id,
    )

    for index, row in enumerate(rows_to_clone):
        session.add(
            _clone_message_row(
                row,
                session_id=fork_session_id,
                task_id=fork_task.id,
                seq=index,
            )
        )

    await compaction_repo.copy_for_fork(
        session,
        source_session_id=source_session_id,
        target_session_id=fork_session_id,
        target_task_id=fork_task.id,
        project_id=source_task.project_id,
        seq_map=seq_map,
    )

    fork_task.current_revision_id = None
    fork_task.current_message_id = None
    await task_repo.update_task(session, fork_task)
    await session.flush()

    return AgentForkResult(
        session_id=fork_session_id,
        task=fork_task,
        state_values=_build_fork_state(
            session_id=fork_session_id,
            task=fork_task,
            model_config=model_config,
        ),
        cloned_message_count=len(rows_to_clone),
    )
