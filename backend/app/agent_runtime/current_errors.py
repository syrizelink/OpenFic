"""Current-turn errors derived from existing runtime persistence."""

from typing import TypedDict

from langgraph.checkpoint.base import CheckpointTuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.graph.llm_invoke import format_error_message
from app.agent_runtime.persistence.errors import PersistenceError
from app.agent_runtime.persistence.child_runs import get_current_child_run_request
from app.agent_runtime.persistence.model import AgentChildRun
from app.agent_runtime.runner.checkpointer import get_checkpointer
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.core.errors import NotFoundError
from app.storage.models.revision import Revision
from app.storage.services import task_service


class CurrentAgentError(TypedDict):
    type: str
    reason: str
    round_id: str


def _checkpoint_error(checkpoint: CheckpointTuple, revision_id: str) -> CurrentAgentError | None:
    values = checkpoint.checkpoint.get("channel_values", {})
    if "current_revision_id" in values and values["current_revision_id"] != revision_id:
        return None
    for write in checkpoint.pending_writes or []:
        if len(write) < 3 or write[1] != "__error__":
            continue
        error = write[2]
        if isinstance(error, BaseException):
            reason = format_error_message(error)
        elif isinstance(error, str):
            reason = error.strip()
        else:
            continue
        if reason:
            return {
                "type": "persistence_failure" if isinstance(error, PersistenceError) else "runtime_failure",
                "reason": reason,
                "round_id": revision_id,
            }
    return None


async def load_session_current_error(
    session: AsyncSession,
    session_id: str,
) -> CurrentAgentError | None:
    try:
        task = await task_service.get_task_by_agent_session_id(session, session_id)
    except NotFoundError:
        return None
    if task.is_running or await get_agent_run_registry().is_running(session_id):
        return None
    revision = await session.get(Revision, task.current_revision_id) if task.current_revision_id else None
    if (
        revision is None
        or revision.status not in {"failed", "interrupted"}
        or revision.agent_session_id != session_id
        or revision.task_id != task.id
    ):
        return None
    saver = await get_checkpointer()
    checkpoint = await saver.aget_tuple({"configurable": {"thread_id": session_id}})
    if checkpoint is None or checkpoint.checkpoint.get("channel_values", {}).get("current_revision_id") != revision.id:
        return None
    error = _checkpoint_error(checkpoint, revision.id)
    if error is not None:
        return error

    # Nested namespaces must belong to a task in the current root checkpoint.
    # Inspect only their newest checkpoint, never an older failed attempt.
    if not checkpoint.pending_writes:
        return None
    latest: dict[str, CheckpointTuple] = {"": checkpoint}
    async for nested in saver.alist({"configurable": {"thread_id": session_id}}):
        namespace = nested.config.get("configurable", {}).get("checkpoint_ns", "")
        latest.setdefault(namespace, nested)
    for namespace in sorted(latest, key=lambda value: value.count("|")):
        if not namespace:
            continue
        nested = latest[namespace]
        parts = namespace.split("|")
        parent_namespace = "|".join(parts[:-1])
        parent = latest.get(parent_namespace)
        values = nested.checkpoint.get("channel_values", {})
        if (
            parent is None
            or parts[-1].rsplit(":", 1)[-1] not in {write[0] for write in parent.pending_writes or []}
            or nested.checkpoint["ts"] < parent.checkpoint["ts"]
            or ("current_revision_id" in values and values["current_revision_id"] != revision.id)
        ):
            latest.pop(namespace)
            continue
        error = _checkpoint_error(nested, revision.id)
        if error is not None:
            return error
    return None


async def load_subagent_current_turn(
    session: AsyncSession,
    child: AgentChildRun,
) -> tuple[str | None, CurrentAgentError | None]:
    request = await get_current_child_run_request(session, child_run_id=child.id)
    if request is None:
        return None, None
    if (
        child.status not in {"queued", "error"}
        or child.pending_approval_json
        or request.status != "error"
    ):
        return request.id, None
    reason = request.error or (child.error if child.status == "error" else None)
    if not reason:
        return request.id, None
    return request.id, {"type": "subagent_failed", "reason": reason, "round_id": request.id}
