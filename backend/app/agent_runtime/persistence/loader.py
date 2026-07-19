"""DB 历史 → ReAct 子图初始 messages。"""

import json

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
            if tool_row.tool_call_id not in {
                tool_call.get("id") for tool_call in tool_calls
            }
        )
        index = next_index
    return ordered


async def load_history(
    db_session: AsyncSession, session_id: str
) -> list[BaseMessage]:
    """加载 session 历史，转成 LangChain BaseMessage 列表。

    规则：
    - 跳过 status=pending 的 user
    - 配对兜底：孤立 tool 行整条丢弃；assistant.tool_calls 中 id 找不到对应 tool 行的项被剔除
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
        if r.role != "tool" or not r.tool_call_id or r.tool_call_id not in tool_call_id_set:
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

    seen_tool_ids: set[str] = set()
    filtered: list[AgentRunMessage] = []
    for r in rows:
        if r.role == "tool":
            if not r.tool_call_id or r.tool_call_id not in tool_call_id_set:
                continue
            if selected_tool_rows.get(r.tool_call_id) is not r:
                continue
            seen_tool_ids.add(r.tool_call_id)
        filtered.append(r)

    filtered = _order_tool_results_by_call_order(filtered)

    last_assistant_with_reasoning_idx: int | None = None
    for idx, r in enumerate(filtered):
        if r.role == "assistant" and r.reasoning:
            last_assistant_with_reasoning_idx = idx

    messages: list[BaseMessage] = []
    for idx, r in enumerate(filtered):
        if r.role == "system":
            messages.append(
                SystemMessage(
                    content=r.content,
                    response_metadata=_response_metadata(r),
                )
            )
        elif r.role == "user":
            messages.append(
                HumanMessage(
                    content=r.content,
                    response_metadata=_response_metadata(r),
                )
            )
        elif r.role == "assistant":
            cleaned_tool_calls = []
            row_tool_calls = _tool_calls(r)
            if row_tool_calls:
                for tc in row_tool_calls:
                    tc_id = tc.get("id")
                    if tc_id and tc_id in seen_tool_ids:
                        cleaned_tool_calls.append(tc)
            kwargs: dict = {}
            if idx == last_assistant_with_reasoning_idx and r.reasoning:
                kwargs["reasoning_content"] = r.reasoning
            ai_msg = AIMessage(
                content=r.content,
                tool_calls=cleaned_tool_calls,
                additional_kwargs=kwargs,
                response_metadata=_response_metadata(r),
            )
            messages.append(ai_msg)
        elif r.role == "tool":
            messages.append(
                ToolMessage(
                    content=r.content,
                    tool_call_id=r.tool_call_id or "",
                    name=r.tool_name or "",
                    response_metadata=_response_metadata(r),
                )
            )
    return messages
