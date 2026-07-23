"""Persistence helpers for PA-owned child runs and parent-session queue items."""

import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence import repo as message_repo
from app.agent_runtime.persistence.model import (
    AgentChildRun,
    AgentChildRunRequest,
)

CHILD_RUN_STATUSES = {
    "queued",
    "running",
    "waiting_user",
    "completed",
    "error",
    "cancelled",
}
CHILD_RUN_REQUEST_STATUSES = {
    "pending",
    "running",
    "completed",
    "error",
    "cancelled",
}
TERMINAL_CHILD_RUN_STATUSES = {"completed", "error", "cancelled"}
TERMINAL_CHILD_RUN_REQUEST_STATUSES = {"completed", "error", "cancelled"}
SUBAGENT_AGENT_NUMBER_MIN = 1000
SUBAGENT_AGENT_NUMBER_MAX = 9999
SUBAGENT_AGENT_NUMBER_SPACE = SUBAGENT_AGENT_NUMBER_MAX - SUBAGENT_AGENT_NUMBER_MIN + 1
_PARENT_SUBAGENT_NUMBER_LOCKS: dict[str, asyncio.Lock] = {}
_PARENT_SUBAGENT_NUMBER_LOCKS_GUARD = asyncio.Lock()


@dataclass(frozen=True)
class ChildRunRollbackResult:
    checkpoint_boundaries: list[tuple[str, str | None]]
    child_run_ids: list[str]


def _ensure_status(value: str, allowed: set[str], field_name: str) -> None:
    if value not in allowed:
        raise ValueError(f"invalid {field_name}: {value}")


def _normalize_agent_number(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if len(stripped) == 5 and stripped.startswith("#") and stripped[1:].isdigit():
            return stripped
    return None


def get_child_run_agent_number(metadata: dict[str, Any] | None) -> str | None:
    if not isinstance(metadata, dict):
        return None
    return _normalize_agent_number(metadata.get("agent_number"))


async def _get_parent_subagent_number_lock(parent_session_id: str) -> asyncio.Lock:
    async with _PARENT_SUBAGENT_NUMBER_LOCKS_GUARD:
        lock = _PARENT_SUBAGENT_NUMBER_LOCKS.get(parent_session_id)
        if lock is None:
            lock = asyncio.Lock()
            _PARENT_SUBAGENT_NUMBER_LOCKS[parent_session_id] = lock
        return lock


async def _allocate_child_run_agent_number(
    session: AsyncSession,
    *,
    parent_session_id: str,
) -> str:
    result = await session.execute(
        select(col(AgentChildRun.metadata_json)).where(
            col(AgentChildRun.parent_session_id) == parent_session_id
        )
    )
    used_numbers = {
        number
        for metadata in result.scalars().all()
        if (number := get_child_run_agent_number(metadata)) is not None
    }
    if len(used_numbers) >= SUBAGENT_AGENT_NUMBER_SPACE:
        raise ValueError("no available subagent agent numbers for parent session")

    while True:
        candidate = f"#{random.randint(SUBAGENT_AGENT_NUMBER_MIN, SUBAGENT_AGENT_NUMBER_MAX):04d}"
        if candidate not in used_numbers:
            return candidate


async def create_child_run(
    session: AsyncSession,
    *,
    parent_session_id: str,
    parent_task_id: str,
    parent_thread_id: str,
    child_thread_id: str,
    agent_key: str,
    dispatch_id: str,
    tool_call_id: str,
    request: dict[str, Any],
    status: str = "queued",
    metadata: dict[str, Any] | None = None,
    parent_revision_id: str | None = None,
    child_user_message_id: str | None = None,
    child_user_message_seq: int | None = None,
    pre_request_checkpoint_id: str | None = None,
) -> AgentChildRun:
    _ensure_status(status, CHILD_RUN_STATUSES, "child run status")
    now = datetime.now(UTC)
    metadata_payload = dict(metadata or {})
    parent_number_lock = None
    if get_child_run_agent_number(metadata_payload) is None:
        parent_number_lock = await _get_parent_subagent_number_lock(parent_session_id)

    if parent_number_lock is not None:
        await parent_number_lock.acquire()
    try:
        if parent_number_lock is not None:
            metadata_payload["agent_number"] = await _allocate_child_run_agent_number(
                session,
                parent_session_id=parent_session_id,
            )
        row = AgentChildRun(
            parent_session_id=parent_session_id,
            parent_task_id=parent_task_id,
            parent_thread_id=parent_thread_id,
            child_thread_id=child_thread_id,
            agent_key=agent_key,
            dispatch_id=dispatch_id,
            tool_call_id=tool_call_id,
            request_json=request,
            status=status,
            is_active=True,
            metadata_json=metadata_payload,
            parent_revision_id=parent_revision_id,
            recycled_at=None,
            last_assistant_content=None,
            last_user_message_at=now,
            last_completed_at=None,
            started_at=now if status in {"running", "waiting_user"} else None,
        )
        initial_request = AgentChildRunRequest(
            child_run_id=row.id,
            parent_session_id=parent_session_id,
            parent_task_id=parent_task_id,
            request_kind="dispatch",
            content=str(request.get("task") or ""),
            status=_initial_request_status(status),
            parent_revision_id=parent_revision_id,
            child_user_message_id=child_user_message_id,
            child_user_message_seq=child_user_message_seq,
            pre_request_checkpoint_id=pre_request_checkpoint_id,
            seq=0,
            started_at=now if status in {"running", "waiting_user"} else None,
            completed_at=now if status in TERMINAL_CHILD_RUN_REQUEST_STATUSES else None,
        )
        session.add(row)
        session.add(initial_request)
        await session.commit()
        await session.refresh(row)
        return row
    finally:
        if parent_number_lock is not None and parent_number_lock.locked():
            parent_number_lock.release()


async def list_child_runs_for_parent(
    session: AsyncSession,
    parent_session_id: str,
) -> list[AgentChildRun]:
    result = await session.execute(
        select(AgentChildRun)
        .where(col(AgentChildRun.parent_session_id) == parent_session_id)
        .order_by(col(AgentChildRun.created_at).asc())
    )
    return list(result.scalars().all())


async def get_child_run_by_pending_approval(
    session: AsyncSession,
    *,
    parent_session_id: str,
    approval_id: str,
) -> AgentChildRun | None:
    result = await session.execute(
        select(AgentChildRun)
        .where(
            col(AgentChildRun.parent_session_id) == parent_session_id,
            col(AgentChildRun.pending_approval_id) == approval_id,
            col(AgentChildRun.status) == "waiting_user",
        )
        .order_by(col(AgentChildRun.updated_at).desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_waiting_child_run_for_tool_call(
    session: AsyncSession,
    *,
    parent_session_id: str,
    tool_call_id: str,
) -> AgentChildRun | None:
    result = await session.execute(
        select(AgentChildRun)
        .where(
            col(AgentChildRun.parent_session_id) == parent_session_id,
            col(AgentChildRun.tool_call_id) == tool_call_id,
            col(AgentChildRun.status) == "waiting_user",
        )
        .order_by(col(AgentChildRun.updated_at).desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_child_run_for_parent_tool_call(
    session: AsyncSession,
    *,
    parent_session_id: str,
    tool_call_id: str,
) -> AgentChildRun | None:
    result = await session.execute(
        select(AgentChildRun)
        .where(
            col(AgentChildRun.parent_session_id) == parent_session_id,
            col(AgentChildRun.tool_call_id) == tool_call_id,
        )
        .order_by(col(AgentChildRun.created_at).desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_child_run_for_parent_dispatch_id(
    session: AsyncSession,
    *,
    parent_session_id: str,
    dispatch_id: str,
) -> AgentChildRun | None:
    result = await session.execute(
        select(AgentChildRun)
        .where(
            col(AgentChildRun.parent_session_id) == parent_session_id,
            col(AgentChildRun.dispatch_id) == dispatch_id,
        )
        .order_by(col(AgentChildRun.created_at).desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_child_run_for_parent(
    session: AsyncSession,
    *,
    parent_session_id: str,
    child_run_id: str | None = None,
    dispatch_id: str | None = None,
) -> AgentChildRun | None:
    if child_run_id:
        row = await session.get(AgentChildRun, child_run_id)
        if row is None or row.parent_session_id != parent_session_id:
            return None
        return row
    if dispatch_id:
        result = await session.execute(
            select(AgentChildRun)
            .where(
                col(AgentChildRun.parent_session_id) == parent_session_id,
                col(AgentChildRun.dispatch_id) == dispatch_id,
            )
            .order_by(col(AgentChildRun.created_at).desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    raise ValueError("child_run_id or dispatch_id is required")


async def get_child_run_request_by_seq(
    session: AsyncSession,
    *,
    child_run_id: str,
    seq: int,
) -> AgentChildRunRequest | None:
    result = await session.execute(
        select(AgentChildRunRequest)
        .where(
            col(AgentChildRunRequest.child_run_id) == child_run_id,
            col(AgentChildRunRequest.seq) == seq,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_running_child_run_request(
    session: AsyncSession,
    *,
    child_run_id: str,
) -> AgentChildRunRequest | None:
    result = await session.execute(
        select(AgentChildRunRequest)
        .where(
            col(AgentChildRunRequest.child_run_id) == child_run_id,
            col(AgentChildRunRequest.status) == "running",
        )
        .order_by(col(AgentChildRunRequest.seq).asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_pending_child_run_requests(
    session: AsyncSession,
    child_run_id: str,
) -> int:
    result = await session.execute(
        select(func.count(col(AgentChildRunRequest.id))).where(
            col(AgentChildRunRequest.child_run_id) == child_run_id,
            col(AgentChildRunRequest.status) == "pending",
        )
    )
    return int(result.scalar_one() or 0)


async def record_child_run_pending_approval(
    session: AsyncSession,
    child_run_id: str,
    *,
    approval_id: str,
    approval_request: dict[str, Any],
    result: dict[str, Any] | None = None,
) -> AgentChildRun:
    row = await session.get(AgentChildRun, child_run_id)
    if row is None:
        raise ValueError(f"child run not found: {child_run_id}")

    row.status = "waiting_user"
    row.pending_approval_id = approval_id
    row.pending_approval_json = approval_request
    if result is not None:
        row.result_json = result
    row.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(row)
    return row


async def update_child_run_status(
    session: AsyncSession,
    child_run_id: str,
    status: str,
    *,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    assistant_content: str | None = None,
    completed_at: datetime | None = None,
) -> AgentChildRun:
    _ensure_status(status, CHILD_RUN_STATUSES, "child run status")
    row = await session.get(AgentChildRun, child_run_id)
    if row is None:
        raise ValueError(f"child run not found: {child_run_id}")

    now = completed_at or datetime.now(UTC)
    row.status = status
    if status == "running":
        row.started_at = now
    if status in TERMINAL_CHILD_RUN_STATUSES:
        row.completed_at = now
        row.pending_approval_id = None
        row.pending_approval_json = None
        row.last_completed_at = now
    if result is not None:
        row.result_json = result
    if error is not None:
        row.error = error
    elif status not in {"error", "waiting_user"}:
        row.error = None
    persisted_assistant_content = assistant_content
    if persisted_assistant_content is None and isinstance(result, dict):
        candidate = result.get("assistant_content")
        if isinstance(candidate, str):
            persisted_assistant_content = candidate
    if persisted_assistant_content is not None:
        row.last_assistant_content = persisted_assistant_content
    row.updated_at = now
    await session.commit()
    await session.refresh(row)
    return row


def _initial_request_status(child_run_status: str) -> str:
    if child_run_status == "queued":
        return "pending"
    if child_run_status in {"running", "waiting_user"}:
        return "running"
    if child_run_status == "completed":
        return "completed"
    if child_run_status == "error":
        return "error"
    if child_run_status == "cancelled":
        return "cancelled"
    raise ValueError(
        f"unsupported child run status for request initialization: {child_run_status}"
    )


async def _next_child_request_seq(session: AsyncSession, child_run_id: str) -> int:
    result = await session.execute(
        select(func.max(col(AgentChildRunRequest.seq))).where(
            col(AgentChildRunRequest.child_run_id) == child_run_id
        )
    )
    max_seq = result.scalar_one_or_none()
    return 0 if max_seq is None else int(max_seq) + 1


async def enqueue_child_run_request(
    session: AsyncSession,
    *,
    child_run_id: str,
    request_kind: str,
    content: str,
    parent_revision_id: str | None = None,
    child_user_message_id: str | None = None,
    child_user_message_seq: int | None = None,
    pre_request_checkpoint_id: str | None = None,
) -> AgentChildRunRequest:
    row = await session.get(AgentChildRun, child_run_id)
    if row is None:
        raise ValueError(f"child run not found: {child_run_id}")
    if not row.is_active:
        raise ValueError(f"child run is inactive: {child_run_id}")

    now = datetime.now(UTC)
    request_row = AgentChildRunRequest(
        child_run_id=row.id,
        parent_session_id=row.parent_session_id,
        parent_task_id=row.parent_task_id,
        request_kind=request_kind,
        content=content,
        status="pending",
        parent_revision_id=parent_revision_id,
        child_user_message_id=child_user_message_id,
        child_user_message_seq=child_user_message_seq,
        pre_request_checkpoint_id=pre_request_checkpoint_id,
        seq=await _next_child_request_seq(session, child_run_id),
    )
    if row.status != "waiting_user":
        row.status = "queued"
    row.last_user_message_at = now
    row.updated_at = now
    session.add(request_row)
    await session.commit()
    await session.refresh(request_row)
    return request_row


async def update_child_run_request_boundaries(
    session: AsyncSession,
    request_id: str,
    *,
    child_user_message_id: str | None = None,
    child_user_message_seq: int | None = None,
    pre_request_checkpoint_id: str | None = None,
) -> AgentChildRunRequest:
    request_row = await session.get(AgentChildRunRequest, request_id)
    if request_row is None:
        raise ValueError(f"child run request not found: {request_id}")
    if child_user_message_id is not None:
        request_row.child_user_message_id = child_user_message_id
    if child_user_message_seq is not None:
        request_row.child_user_message_seq = child_user_message_seq
    if pre_request_checkpoint_id is not None:
        request_row.pre_request_checkpoint_id = pre_request_checkpoint_id
    request_row.updated_at = datetime.now(UTC)
    session.add(request_row)
    await session.commit()
    await session.refresh(request_row)
    return request_row


async def rollback_child_runs_for_parent_revisions(
    session: AsyncSession,
    *,
    parent_revision_ids: list[str],
) -> ChildRunRollbackResult:
    if not parent_revision_ids:
        return ChildRunRollbackResult(checkpoint_boundaries=[], child_run_ids=[])

    result = await session.execute(
        select(AgentChildRunRequest)
        .where(col(AgentChildRunRequest.parent_revision_id).in_(parent_revision_ids))
        .order_by(
            col(AgentChildRunRequest.child_run_id).asc(),
            col(AgentChildRunRequest.seq).asc(),
        )
    )
    grouped: dict[str, AgentChildRunRequest] = {}
    for request_row in result.scalars().all():
        grouped.setdefault(request_row.child_run_id, request_row)

    checkpoint_boundaries: list[tuple[str, str | None]] = []
    child_run_ids: list[str] = []
    now = datetime.now(UTC)
    for child_run_id, first_request in grouped.items():
        row = await session.get(AgentChildRun, child_run_id)
        if row is None:
            continue
        child_run_ids.append(child_run_id)

        if first_request.child_user_message_seq is not None:
            await message_repo.delete_from_seq(
                session,
                row.child_thread_id,
                first_request.child_user_message_seq,
            )
        if first_request.pre_request_checkpoint_id:
            checkpoint_boundaries.append(
                (row.child_thread_id, first_request.pre_request_checkpoint_id)
            )
        elif first_request.seq == 0:
            checkpoint_boundaries.append((row.child_thread_id, None))

        affected = await session.execute(
            select(AgentChildRunRequest).where(
                col(AgentChildRunRequest.child_run_id) == child_run_id,
                col(AgentChildRunRequest.seq) >= first_request.seq,
            )
        )
        for request_row in affected.scalars().all():
            request_row.status = "cancelled"
            request_row.error = "parent revision rolled back"
            request_row.completed_at = now
            request_row.updated_at = now

        previous_result = await session.execute(
            select(AgentChildRunRequest)
            .where(
                col(AgentChildRunRequest.child_run_id) == child_run_id,
                col(AgentChildRunRequest.seq) < first_request.seq,
                col(AgentChildRunRequest.status) == "completed",
            )
            .order_by(col(AgentChildRunRequest.seq).desc())
            .limit(1)
        )
        previous = previous_result.scalar_one_or_none()
        row.pending_approval_id = None
        row.pending_approval_json = None
        row.updated_at = now
        if first_request.seq == 0:
            row.is_active = False
            row.status = "cancelled"
            row.completed_at = now
            row.last_completed_at = now
            row.last_assistant_content = None
            row.error = "parent revision rolled back"
        else:
            row.is_active = True
            row.status = "completed" if previous is not None else "queued"
            row.last_assistant_content = (
                previous.assistant_content if previous else None
            )
            row.last_completed_at = previous.completed_at if previous else None
            row.error = None

    await session.flush()
    return ChildRunRollbackResult(
        checkpoint_boundaries=list(dict.fromkeys(checkpoint_boundaries)),
        child_run_ids=list(dict.fromkeys(child_run_ids)),
    )


async def claim_next_child_run_request(
    session: AsyncSession,
    child_run_id: str,
) -> AgentChildRunRequest | None:
    row = await session.get(AgentChildRun, child_run_id)
    if row is None:
        raise ValueError(f"child run not found: {child_run_id}")
    if not row.is_active:
        return None
    if row.pending_approval_id or row.status == "waiting_user":
        return None

    result = await session.execute(
        select(AgentChildRunRequest)
        .where(
            col(AgentChildRunRequest.child_run_id) == child_run_id,
            col(AgentChildRunRequest.status) == "pending",
        )
        .order_by(col(AgentChildRunRequest.seq).asc())
        .limit(1)
    )
    request_row = result.scalar_one_or_none()
    if request_row is None:
        return None

    now = datetime.now(UTC)
    request_row.status = "running"
    request_row.started_at = now
    request_row.updated_at = now
    row.status = "running"
    row.started_at = now
    row.updated_at = now
    await session.commit()
    await session.refresh(request_row)
    return request_row


async def complete_child_run_request(
    session: AsyncSession,
    request_id: str,
    *,
    status: str = "completed",
    assistant_content: str | None = None,
    error: str | None = None,
    completed_at: datetime | None = None,
) -> AgentChildRunRequest:
    _ensure_status(status, CHILD_RUN_REQUEST_STATUSES, "child run request status")
    if status not in TERMINAL_CHILD_RUN_REQUEST_STATUSES:
        raise ValueError(
            f"child run request must complete with terminal status: {status}"
        )

    request_row = await session.get(AgentChildRunRequest, request_id)
    if request_row is None:
        raise ValueError(f"child run request not found: {request_id}")

    row = await session.get(AgentChildRun, request_row.child_run_id)
    if row is None:
        raise ValueError(f"child run not found: {request_row.child_run_id}")

    now = completed_at or datetime.now(UTC)
    request_row.status = status
    request_row.assistant_content = assistant_content
    if error is not None:
        request_row.error = error
    request_row.completed_at = now
    request_row.updated_at = now

    if assistant_content is not None:
        row.last_assistant_content = assistant_content
    row.pending_approval_id = None
    row.pending_approval_json = None
    row.last_completed_at = now
    row.updated_at = now

    pending_exists = await _child_has_pending_requests(
        session, row.id, exclude_request_id=request_id
    )
    if status == "completed" and pending_exists and row.is_active:
        row.status = "queued"
    else:
        row.status = "completed" if status == "completed" else status

    await session.commit()
    await session.refresh(request_row)
    return request_row


async def cancel_child_run_request(
    session: AsyncSession,
    request_id: str,
    *,
    error: str | None = None,
) -> AgentChildRunRequest:
    return await complete_child_run_request(
        session,
        request_id,
        status="cancelled",
        error=error,
    )


async def _cancel_open_child_run_requests(
    session: AsyncSession,
    *,
    child_run_id: str,
    now: datetime,
    error: str | None = None,
) -> None:
    cancel_result = await session.execute(
        select(AgentChildRunRequest).where(
            col(AgentChildRunRequest.child_run_id) == child_run_id,
            col(AgentChildRunRequest.status).in_(("pending", "running")),
        )
    )
    for request_row in cancel_result.scalars().all():
        request_row.status = "cancelled"
        if error is not None:
            request_row.error = error
        request_row.completed_at = now
        request_row.updated_at = now


async def cancel_child_run(
    session: AsyncSession,
    child_run_id: str,
    *,
    error: str | None = None,
) -> AgentChildRun:
    row = await session.get(AgentChildRun, child_run_id)
    if row is None:
        raise ValueError(f"child run not found: {child_run_id}")

    now = datetime.now(UTC)
    await _cancel_open_child_run_requests(
        session,
        child_run_id=child_run_id,
        now=now,
        error=error,
    )

    row.status = "cancelled"
    row.pending_approval_id = None
    row.pending_approval_json = None
    row.completed_at = now
    row.last_completed_at = now
    if error is not None:
        row.error = error
    row.updated_at = now
    await session.commit()
    await session.refresh(row)
    return row


async def recycle_child_run(
    session: AsyncSession,
    child_run_id: str,
    *,
    error: str | None = None,
) -> AgentChildRun:
    row = await session.get(AgentChildRun, child_run_id)
    if row is None:
        raise ValueError(f"child run not found: {child_run_id}")

    now = datetime.now(UTC)
    await _cancel_open_child_run_requests(
        session,
        child_run_id=child_run_id,
        now=now,
        error=error,
    )

    row.is_active = False
    row.recycled_at = now
    row.status = "cancelled"
    row.pending_approval_id = None
    row.pending_approval_json = None
    row.completed_at = now
    row.last_completed_at = now
    if error is not None:
        row.error = error
    row.updated_at = now
    await session.commit()
    await session.refresh(row)
    return row


async def list_active_child_runs(
    session: AsyncSession,
    *,
    parent_session_id: str,
) -> list[AgentChildRun]:
    result = await session.execute(
        select(AgentChildRun)
        .where(
            col(AgentChildRun.parent_session_id) == parent_session_id,
            col(AgentChildRun.is_active).is_(True),
        )
        .order_by(col(AgentChildRun.created_at).asc())
    )
    return list(result.scalars().all())


async def _child_has_pending_requests(
    session: AsyncSession,
    child_run_id: str,
    *,
    exclude_request_id: str | None = None,
) -> bool:
    query = select(col(AgentChildRunRequest.id)).where(
        col(AgentChildRunRequest.child_run_id) == child_run_id,
        col(AgentChildRunRequest.status) == "pending",
    )
    if exclude_request_id is not None:
        query = query.where(col(AgentChildRunRequest.id) != exclude_request_id)
    result = await session.execute(query.limit(1))
    return result.scalar_one_or_none() is not None
