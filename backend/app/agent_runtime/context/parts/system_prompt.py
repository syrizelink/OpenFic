from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context.errors import ContextBuildError
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.graph.state import AgentRuntimeState
from app.macro.compiler import EntryInput, PromptChainCompiler
from app.storage.services import prompt_chain_service


async def build_system_prompt(
    state: AgentRuntimeState,
    agent_name: str,
    db_session: AsyncSession,
) -> list[ContextMessage]:
    """构建 p1 PromptChain，并保留各 entry 的原始 role。"""
    builtin_agent_names = {"primary", "explorer", "composer", "auditor", "writer", "actor", "reviewer"}
    prompt_id = (
        f"builtin-agent--{agent_name}"
        if agent_name in builtin_agent_names
        else f"custom-agent--{agent_name}"
    )

    try:
        version = await prompt_chain_service.get_latest_version_with_entries_or_default(
            db_session,
            prompt_id=prompt_id,
        )
    except Exception as e:
        raise ContextBuildError(
            "system_prompt",
            f"failed to load prompt chain (prompt_id={prompt_id})",
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
