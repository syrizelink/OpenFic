from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.types import ContextMessage


def to_langchain_messages(parts: list[ContextMessage]) -> list[BaseMessage]:
    """将 ContextMessage 列表按 role 映射为 LangChain BaseMessage 列表。"""
    out: list[BaseMessage] = []
    for p in parts:
        if p.role == "system":
            out.append(SystemMessage(content=p.content))
        elif p.role == "user":
            out.append(HumanMessage(content=p.content))
        elif p.role == "assistant":
            out.append(
                AIMessage(
                    content=p.content,
                    tool_calls=p.tool_calls or [],
                    additional_kwargs=p.additional_kwargs or {},
                )
            )
        elif p.role == "tool":
            if not p.tool_call_id:
                raise ContextBuildError(
                    "to_langchain", "tool message missing tool_call_id"
                )
            out.append(
                ToolMessage(content=p.content, tool_call_id=p.tool_call_id)
            )
        else:
            raise ContextBuildError(
                "to_langchain", f"unknown role: {p.role}"
            )
    return out
