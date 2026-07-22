"""Project agent runtime messages into TaskMessage API records."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import repo
from app.agent_runtime.persistence.types import PersistedMessage
from app.api.schemas.task import TaskMessage


SUBAGENT_AGENT_IDS = {"explore", "composer", "auditor", "writer", "actor", "reviewer"}
SUBAGENT_ORCHESTRATION_TOOL_NAMES = {
    "dispatch_subagent",
    "notify_subagent",
    "recycle_subagent",
}


def _message_status(status: str) -> str:
    if status in {"sent", "complete"}:
        return "completed"
    if status == "partial":
        return "completed"
    if status == "aborted":
        return "error"
    return status


def _parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _tool_result(row: PersistedMessage) -> dict[str, Any]:
    parsed = _parse_json(row.content)
    if isinstance(parsed, dict):
        success = parsed.get("success")
        error = parsed.get("error")
        message = parsed.get("message") or error
        return {
            **parsed,
            "success": bool(success) if isinstance(success, bool) else not error,
            "type": parsed.get("type") or ("fail" if error else "ok"),
            "reason": parsed.get("reason") or ("tool_error" if error else None),
            "message": message,
            "data": parsed.get("data") if "data" in parsed else parsed,
            "tool_call_id": parsed.get("tool_call_id") or row.tool_call_id,
            "tool_name": parsed.get("tool_name") or row.tool_name,
        }
    return {
        "type": "ok",
        "success": row.status != "aborted",
        "data": parsed,
        "tool_call_id": row.tool_call_id,
        "tool_name": row.tool_name,
    }


def _tool_message_status(row: PersistedMessage, tool_result: dict[str, Any]) -> str:
    if tool_result.get("reason") == "approval_preview":
        return "completed"
    return _message_status(row.status)


def _node_event_payload(row: PersistedMessage) -> dict[str, Any]:
    metadata = row.metadata
    status = metadata.get("node_status")
    if status not in {"running", "completed", "error"}:
        status = (
            "running"
            if row.message_type == "node_start"
            else _message_status(row.status)
        )
    phase = metadata.get("phase")
    if phase not in {"start", "end"}:
        phase = "start" if row.message_type == "node_start" else "end"
    return {
        "node": metadata.get("node") or row.agent_id,
        "phase": phase,
        "status": status,
        "current_node": metadata.get("current_node"),
        "previous_node": metadata.get("previous_node"),
    }


def _is_node_end(row: PersistedMessage) -> bool:
    return row.message_type == "node_end"


def _is_tool_result(row: PersistedMessage) -> bool:
    return row.role == "tool"


def _subagent_tool_call_ids(rows: list[PersistedMessage]) -> set[str]:
    tool_call_ids: set[str] = set()
    for row in rows:
        if row.role != "assistant" or row.agent_id not in SUBAGENT_AGENT_IDS:
            continue
        for tool_call in row.tool_calls or []:
            tool_call_id = tool_call.get("id")
            if isinstance(tool_call_id, str) and tool_call_id:
                tool_call_ids.add(tool_call_id)
    return tool_call_ids


def _has_dispatch_subagent(rows: list[PersistedMessage]) -> bool:
    for row in rows:
        if row.tool_name in SUBAGENT_ORCHESTRATION_TOOL_NAMES:
            return True
        for tool_call in row.tool_calls or []:
            if tool_call.get("name") in SUBAGENT_ORCHESTRATION_TOOL_NAMES:
                return True
    return False


def _is_subagent_internal_row(
    row: PersistedMessage,
    subagent_tool_call_ids: set[str],
) -> bool:
    if row.agent_id in SUBAGENT_AGENT_IDS:
        return True
    return bool(row.role == "tool" and row.tool_call_id in subagent_tool_call_ids)


def _projection_order(rows: list[PersistedMessage]) -> list[PersistedMessage]:
    ordered: list[PersistedMessage] = []
    index = 0
    while index < len(rows):
        row = rows[index]
        next_row = rows[index + 1] if index + 1 < len(rows) else None
        if next_row is not None and _is_node_end(row) and _is_tool_result(next_row):
            ordered.append(next_row)
            ordered.append(row)
            index += 2
            continue
        ordered.append(row)
        index += 1
    return ordered


def _base_message(
    row: PersistedMessage,
    *,
    message_id: str | None = None,
    role: str | None = None,
    content: str | None = None,
    message_type: str | None = None,
    message_status: str | None = None,
    display_channel: str | None = None,
    payload: dict[str, Any] | None = None,
    tool_calls: list[dict] | None = None,
) -> TaskMessage:
    return TaskMessage(
        id=message_id or row.id,
        task_id=row.task_id,
        role=role or row.role,
        agent_id=row.agent_id,
        content=row.content if content is None else content,
        tool_calls=tool_calls or [],
        tool_call_id=row.tool_call_id,
        metadata=row.metadata,
        message_type=message_type,
        message_status=message_status or _message_status(row.status),
        display_channel=display_channel,
        payload=payload or {},
        correlation_id=row.tool_call_id or row.id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _append_projected_tool_message(
    projected: list[TaskMessage],
    projected_tool_index_by_id: dict[str, int],
    message: TaskMessage,
) -> None:
    tool_call_id = message.tool_call_id
    if not tool_call_id:
        projected.append(message)
        return

    existing_index = projected_tool_index_by_id.get(tool_call_id)
    if existing_index is None:
        projected_tool_index_by_id[tool_call_id] = len(projected)
        projected.append(message)
        return

    existing_message = projected[existing_index]
    projected[existing_index] = message.model_copy(
        update={
            "id": existing_message.id,
            "correlation_id": existing_message.correlation_id,
            "created_at": existing_message.created_at,
        }
    )


def _project_rows(rows: list[PersistedMessage]) -> list[TaskMessage]:
    if _has_dispatch_subagent(rows):
        subagent_tool_call_ids = _subagent_tool_call_ids(rows)
        rows = [
            row
            for row in rows
            if not _is_subagent_internal_row(row, subagent_tool_call_ids)
        ]
    rows = _projection_order(rows)
    tool_args_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.role != "assistant" or not row.tool_calls:
            continue
        for tool_call in row.tool_calls:
            tool_call_id = tool_call.get("id")
            args = tool_call.get("args")
            if isinstance(tool_call_id, str) and isinstance(args, dict):
                tool_args_by_id[tool_call_id] = args

    projected: list[TaskMessage] = []
    projected_tool_index_by_id: dict[str, int] = {}
    for row in rows:
        if row.message_type == "compaction":
            projected.append(
                _base_message(
                    row,
                    message_type="compaction",
                    display_channel=row.display_channel,
                    payload={"kind": "compaction"},
                    tool_calls=[],
                )
            )
            continue

        if row.message_type in {"node_start", "node_end"}:
            payload = _node_event_payload(row)
            status = payload.get("status")
            projected.append(
                _base_message(
                    row,
                    message_type=row.message_type,
                    message_status=status if isinstance(status, str) else None,
                    display_channel=row.display_channel,
                    payload=payload,
                    tool_calls=[],
                )
            )
            continue

        if row.role == "user":
            revision_id = row.metadata.get("revision_id")
            payload = {"kind": "user_request"}
            if isinstance(revision_id, str) and revision_id:
                payload["revision_id"] = revision_id
            projected.append(
                _base_message(
                    row,
                    message_type="user_request",
                    display_channel=row.display_channel,
                    payload=payload,
                )
            )
            continue

        if row.role == "assistant":
            if row.reasoning:
                payload = {"kind": "reasoning"}
                if isinstance(row.reasoning_duration_ms, int):
                    payload["duration_ms"] = row.reasoning_duration_ms
                projected.append(
                    _base_message(
                        row,
                        message_id=f"{row.id}:reasoning",
                        content=row.reasoning,
                        message_type="reasoning",
                        display_channel="list",
                        payload=payload,
                        tool_calls=[],
                    )
                )
            if row.content:
                projected.append(
                    _base_message(
                        row,
                        message_id=f"{row.id}:text",
                        content=row.content,
                        message_type="text",
                        display_channel="list",
                        payload={"kind": "assistant_output"},
                        tool_calls=[],
                    )
                )
            if row.tool_calls:
                projected.append(
                    _base_message(
                        row,
                        message_id=f"{row.id}:tool-calls",
                        content="",
                        tool_calls=row.tool_calls,
                    )
                )
            continue

        if row.role == "tool":
            tool_args = tool_args_by_id.get(row.tool_call_id or "", {})
            tool_result = _tool_result(row)
            _append_projected_tool_message(
                projected,
                projected_tool_index_by_id,
                _base_message(
                    row,
                    message_type="tool",
                    message_status=_tool_message_status(row, tool_result),
                    display_channel="list",
                    payload={
                        "tool_call_id": row.tool_call_id,
                        "tool_name": row.tool_name,
                        "tool_args": tool_args,
                        "tool_args_text": json.dumps(tool_args, ensure_ascii=False),
                        "tool_result": tool_result,
                        "success": bool(tool_result.get("success"))
                        if isinstance(tool_result.get("success"), bool)
                        else row.status != "aborted",
                    },
                ),
            )
            continue

        projected.append(_base_message(row))

    return projected


async def load_task_messages_for_agent_session(
    session: AsyncSession,
    session_id: str,
) -> list[TaskMessage]:
    rows = await repo.list_by_session(session, session_id)
    return _project_rows(rows)
