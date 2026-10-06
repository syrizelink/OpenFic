from collections.abc import Iterator
from dataclasses import replace

from app.agent_runtime.context.compaction.tokens import count_text_tokens
from app.agent_runtime.context.types import ContextMessage

PRUNE_PROTECTED_TOKENS = 100_000
PRUNE_MINIMUM_TOKENS = 20_000
OLD_TOOL_OUTPUT_PLACEHOLDER = "[Old tool result content cleared]"
_PROTECTED_TOOL_NAMES = frozenset(
    {
        "skill",
        "activate_skill",
        "reference_skill",
        "dispatch_subagent",
        "notify_subagent",
    }
)


def _is_history(message: ContextMessage) -> bool:
    return (message.metadata or {}).get("part") == "history"


def _is_pruned(message: ContextMessage) -> bool:
    return (message.metadata or {}).get("pruned") is True


def _is_compaction_summary(message: ContextMessage) -> bool:
    return bool((message.metadata or {}).get("compaction_id"))


def _is_completed_tool(message: ContextMessage) -> bool:
    status = (message.metadata or {}).get("status")
    return status in {None, "complete"}


def _with_pruned_marker(message: ContextMessage) -> ContextMessage:
    metadata = dict(message.metadata or {})
    metadata["pruned"] = True
    return replace(
        message,
        content=OLD_TOOL_OUTPUT_PLACEHOLDER,
        metadata=metadata,
    )


def _reverse_history_units(
    parts: list[ContextMessage],
) -> Iterator[tuple[int | None, tuple[int, ...]]]:
    index = len(parts) - 1
    while index >= 0:
        message = parts[index]
        if not _is_history(message):
            index -= 1
            continue

        if message.role != "tool":
            yield index, ()
            index -= 1
            continue

        tool_indices: list[int] = []
        while (
            index >= 0
            and _is_history(parts[index])
            and parts[index].role == "tool"
        ):
            tool_indices.append(index)
            index -= 1

        if (
            index >= 0
            and _is_history(parts[index])
            and parts[index].role == "assistant"
        ):
            assistant_index = index
            index -= 1
            yield assistant_index, tuple(tool_indices)
            continue

        for tool_index in tool_indices:
            yield None, (tool_index,)


def prune_tool_outputs(
    parts: list[ContextMessage],
    *,
    protected_tokens: int = PRUNE_PROTECTED_TOKENS,
    minimum_tokens: int = PRUNE_MINIMUM_TOKENS,
) -> list[ContextMessage]:
    """Replace sufficiently old tool outputs with model-visible placeholders."""
    total_tokens = 0
    pruned_tokens = 0
    candidates: list[int] = []
    turns = 0
    steps = 0
    recent = True

    for assistant_index, tool_indices in _reverse_history_units(parts):
        message = parts[assistant_index] if assistant_index is not None else None
        if message is not None:
            if message.role == "user":
                turns += 1
            elif message.role == "assistant":
                steps += 1

            if _is_compaction_summary(message):
                recent = False

        if message is not None and _is_compaction_summary(message):
            if turns >= 2:
                break
            continue

        if turns < 2 and (not recent or steps <= 2):
            continue

        stop = False
        for index in tool_indices:
            tool = parts[index]
            if _is_pruned(tool):
                stop = True
                break
            if not _is_completed_tool(tool):
                continue
            if tool.name in _PROTECTED_TOOL_NAMES:
                continue
            if not tool.tool_call_id:
                continue

            output_tokens = count_text_tokens(tool.content)
            total_tokens += output_tokens
            if total_tokens <= protected_tokens:
                continue

            pruned_tokens += output_tokens
            candidates.append(index)
        if stop:
            break

    if pruned_tokens <= minimum_tokens:
        return parts

    result = list(parts)
    for index in candidates:
        result[index] = _with_pruned_marker(result[index])
    return result
