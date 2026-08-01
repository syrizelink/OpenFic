"""DB 历史 → ReAct 子图初始 messages。"""

import json
from typing import Literal, cast

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence.errors import PersistenceLoadError
from app.agent_runtime.persistence.model import AgentRunMessage
from app.agent_runtime.context.processors.filter import filter_invalid
from app.agent_runtime.context.types import ContextMessage


def _is_llm_history_message(row: AgentRunMessage) -> bool:
    return row.message_type == "message" and row.llm_visibility == "visible"


def _tool_calls(row: AgentRunMessage) -> list[dict] | None:
    if not row.tool_calls:
        return None
    return json.loads(row.tool_calls)


def _response_metadata(row: AgentRunMessage) -> dict:
    metadata: dict = {"openfic_seq": row.seq}
    if row.role == "tool" and row.tool_name:
        metadata["openfic_tool_name"] = row.tool_name
    return metadata


def _user_additional_kwargs(row: AgentRunMessage) -> dict:
    try:
        metadata = json.loads(row.message_metadata or "{}")
    except (TypeError, ValueError):
        return {}
    attachments = metadata.get("attachments") if isinstance(metadata, dict) else None
    return {"openfic_attachments": attachments} if isinstance(attachments, list) else {}


def _order_tool_results_by_call_order(
    rows: list[AgentRunMessage],
) -> list[AgentRunMessage]:
    """将同一 assistant 消息后的并行工具结果恢复为声明顺序。"""
    ordered: list[AgentRunMessage] = []
    index = 0
    while index < len(rows):
        row = rows[index]
        ordered.append(row)
        tool_calls = _tool_calls(row) if row.role == "assistant" else None
        if not tool_calls:
            index += 1
            continue

        tool_rows: list[AgentRunMessage] = []
        next_index = index + 1
        while next_index < len(rows) and rows[next_index].role == "tool":
            tool_rows.append(rows[next_index])
            next_index += 1

        tool_rows_by_id = {
            tool_row.tool_call_id: tool_row
            for tool_row in tool_rows
            if tool_row.tool_call_id
        }
        ordered.extend(
            tool_rows_by_id[tool_call["id"]]
            for tool_call in tool_calls
            if tool_call.get("id") in tool_rows_by_id
        )
        ordered.extend(
            tool_row
            for tool_row in tool_rows
            if tool_row.tool_call_id
            not in {tool_call.get("id") for tool_call in tool_calls}
        )
        index = next_index
    return ordered


async def load_history(db_session: AsyncSession, session_id: str) -> list[BaseMessage]:
    """加载 session 历史，转成 LangChain BaseMessage 列表。

    规则：
    - 跳过 status=pending 的 user
    - 配对兜底：仅保留 assistant 工具调用及其连续的完整 tool 响应组
    - reasoning 仅注入最近一条 assistant 的 additional_kwargs["reasoning_content"]
    - partial / aborted 仍作为合法历史保留
    """
    try:
        result = await db_session.execute(
            select(AgentRunMessage)
            .where(col(AgentRunMessage.session_id) == session_id)
            .order_by(col(AgentRunMessage.seq).asc())
        )
        raw_rows = list(result.scalars().all())
    except Exception as e:
        raise PersistenceLoadError(
            f"load_history failed for session {session_id}"
        ) from e
    rows = raw_rows
    rows = [
        r
        for r in rows
        if _is_llm_history_message(r)
        and not (r.role == "user" and r.status == "pending")
    ]

    tool_call_id_set: set[str] = set()
    for r in rows:
        row_tool_calls = _tool_calls(r)
        if r.role == "assistant" and row_tool_calls:
            for tc in row_tool_calls:
                tc_id = tc.get("id")
                if tc_id:
                    tool_call_id_set.add(tc_id)

    selected_tool_rows: dict[str, AgentRunMessage] = {}
    for r in rows:
        if (
            r.role != "tool"
            or not r.tool_call_id
            or r.tool_call_id not in tool_call_id_set
        ):
            continue
        existing = selected_tool_rows.get(r.tool_call_id)
        if existing is None:
            selected_tool_rows[r.tool_call_id] = r
            continue
        if existing.status == "aborted" and r.status != "aborted":
            selected_tool_rows[r.tool_call_id] = r
            continue
        if existing.status != "aborted" and r.status == "aborted":
            continue
        selected_tool_rows[r.tool_call_id] = r

    filtered: list[AgentRunMessage] = []
    for r in rows:
        if r.role == "tool":
            if not r.tool_call_id or r.tool_call_id not in tool_call_id_set:
                continue
            if selected_tool_rows.get(r.tool_call_id) is not r:
                continue
        filtered.append(r)

    filtered = _order_tool_results_by_call_order(filtered)

    history_parts = [
        ContextMessage(
            role=cast(Literal["system", "user", "assistant", "tool"], row.role),
            content=row.content,
            name=row.tool_name if row.role == "tool" else None,
            tool_call_id=row.tool_call_id,
            tool_calls=_tool_calls(row),
            metadata={"part": "history", "row": row},
        )
        for row in filtered
        if row.role in {"system", "user", "assistant", "tool"}
    ]
    history_parts = filter_invalid(history_parts)

    def history_row(part: ContextMessage) -> AgentRunMessage:
        return cast(AgentRunMessage, (part.metadata or {})["row"])

    last_assistant_with_reasoning_idx: int | None = None
    for idx, part in enumerate(history_parts):
        row = history_row(part)
        if part.role == "assistant" and row.reasoning:
            last_assistant_with_reasoning_idx = idx

    messages: list[BaseMessage] = []
    for idx, part in enumerate(history_parts):
        row = history_row(part)
        if part.role == "system":
            messages.append(
                SystemMessage(
                    content=part.content,
                    response_metadata=_response_metadata(row),
                )
            )
        elif part.role == "user":
            messages.append(
                HumanMessage(
                    content=part.content,
                    additional_kwargs=_user_additional_kwargs(row),
                    response_metadata=_response_metadata(row),
                )
            )
        elif part.role == "assistant":
            kwargs: dict = {}
            if idx == last_assistant_with_reasoning_idx and row.reasoning:
                kwargs["reasoning_content"] = row.reasoning
            ai_msg = AIMessage(
                content=part.content,
                tool_calls=part.tool_calls or [],
                additional_kwargs=kwargs,
                response_metadata=_response_metadata(row),
            )
            messages.append(ai_msg)
        elif part.role == "tool":
            messages.append(
                ToolMessage(
                    content=part.content,
                    tool_call_id=part.tool_call_id or "",
                    name=part.name or "",
                    response_metadata=_response_metadata(row),
                )
            )
    return messages
