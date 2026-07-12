from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.graph.state import AgentRuntimeState
from app.macro.compiler import EntryInput, PromptChainCompiler
from app.storage.services import prompt_chain_service


def _resolve_mode(state: AgentRuntimeState) -> str:
    return "assistant"


async def build_system_prompt(
    state: AgentRuntimeState,
    agent_name: str,
    db_session: AsyncSession,
) -> list[ContextMessage]:
    """构建 p1 PromptChain，并保留各 entry 的原始 role。"""
    mode_name = _resolve_mode(state)
    task_name = "agent"

    try:
        version = await prompt_chain_service.get_latest_version_with_entries_or_default(
            db_session,
            mode_name=mode_name,
            task_name=task_name,
            agent_name=agent_name,
        )
    except Exception as e:
        raise ContextBuildError(
            "system_prompt",
            f"failed to load prompt chain (mode={mode_name}, task={task_name}, agent={agent_name})",
            cause=e,
        ) from e

    enabled_entries = [
        EntryInput(
            role=e.role,
            content=e.content,
            order_index=e.order_index,
            is_enabled=e.is_enabled,
        )
        for e in version.entries
        if e.is_enabled
    ]

    if not enabled_entries:
        return []

    compiler = PromptChainCompiler()
    try:
        compile_result = await compiler.compile(enabled_entries)
    except Exception as e:
        raise ContextBuildError("system_prompt", "compile failed", cause=e) from e

    messages: list[ContextMessage] = []
    for entry in compile_result.entries:
        if not entry.content:
            continue
        if entry.role not in {"system", "user", "assistant"}:
            raise ContextBuildError(
                "system_prompt",
                f"unsupported prompt chain role: {entry.role}",
            )
        messages.append(
            ContextMessage(
                role=cast(Literal["system", "user", "assistant"], entry.role),
                content=entry.content,
                metadata={"part": "system_prompt"},
            )
        )

    return messages
