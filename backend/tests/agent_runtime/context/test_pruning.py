from app.agent_runtime.context.pruning import (
    OLD_TOOL_OUTPUT_PLACEHOLDER,
    PRUNE_MINIMUM_TOKENS,
    PRUNE_PROTECTED_TOKENS,
    prune_tool_outputs,
)
from app.agent_runtime.context.types import ContextMessage


def _history(
    role: str,
    content: str,
    *,
    seq: int,
    tool_call_id: str | None = None,
    name: str | None = None,
    pruned: bool = False,
    status: str | None = None,
) -> ContextMessage:
    metadata = {"part": "history", "seq": seq}
    if pruned:
        metadata["pruned"] = True
    if status is not None:
        metadata["status"] = status
    return ContextMessage(
        role=role,  # type: ignore[arg-type]
        content=content,
        tool_call_id=tool_call_id,
        name=name,
        metadata=metadata,
    )


def _step(index: int, output: str, *, tool_name: str = "bash") -> list[ContextMessage]:
    return [
        _history("assistant", f"step-{index}", seq=index * 3),
        _history(
            "tool",
            output,
            seq=index * 3 + 1,
            tool_call_id=f"call-{index}",
            name=tool_name,
        ),
    ]


def _multi_turn_history(*outputs: tuple[str, str]) -> list[ContextMessage]:
    messages: list[ContextMessage] = []
    for index, (tool_name, output) in enumerate(outputs, start=1):
        messages.append(_history("user", f"user-{index}", seq=index * 3 - 2))
        messages.extend(_step(index, output, tool_name=tool_name))
    return messages


def test_prunes_old_tool_outputs_after_the_protected_budget(monkeypatch) -> None:
    sizes = {
        "old": PRUNE_PROTECTED_TOKENS + 1,
        "older": PRUNE_MINIMUM_TOKENS + 1,
        "recent": PRUNE_PROTECTED_TOKENS + 1,
    }
    monkeypatch.setattr(
        "app.agent_runtime.context.pruning.count_text_tokens",
        lambda content: sizes[content],
    )
    parts = _multi_turn_history(
        ("bash", "older"),
        ("bash", "old"),
        ("bash", "recent"),
        ("bash", "recent"),
    )

    result = prune_tool_outputs(parts)

    pruned = [part for part in result if part.metadata and part.metadata.get("pruned")]
    assert [part.tool_call_id for part in pruned] == ["call-1", "call-2"]
    assert all(part.content == OLD_TOOL_OUTPUT_PLACEHOLDER for part in pruned)


def test_pruning_uses_configured_budgets(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.agent_runtime.context.pruning.count_text_tokens",
        lambda content: {"old": 15, "recent": 15}[content],
    )
    parts = _multi_turn_history(
        ("bash", "old"), ("bash", "recent"), ("bash", "recent")
    )
    result = prune_tool_outputs(parts, protected_tokens=10, minimum_tokens=5)
    assert [part.tool_call_id for part in result if (part.metadata or {}).get("pruned")] == ["call-1"]


def test_does_not_prune_when_excess_budget_is_exactly_twenty_thousand(monkeypatch) -> None:
    sizes = {
        "old-near": PRUNE_PROTECTED_TOKENS - PRUNE_MINIMUM_TOKENS + 1,
        "old-exact": PRUNE_MINIMUM_TOKENS,
        "recent": PRUNE_PROTECTED_TOKENS + 1,
    }
    monkeypatch.setattr(
        "app.agent_runtime.context.pruning.count_text_tokens",
        lambda content: sizes[content],
    )
    parts = _multi_turn_history(
        ("bash", "old-exact"),
        ("bash", "old-near"),
        ("bash", "recent"),
        ("bash", "recent"),
    )

    result = prune_tool_outputs(parts)

    assert result == parts


def test_preserves_recent_steps_and_skill_outputs(monkeypatch) -> None:
    sizes = {
        "old": PRUNE_PROTECTED_TOKENS + PRUNE_MINIMUM_TOKENS + 1,
        "recent": PRUNE_PROTECTED_TOKENS + 1,
        "skill": PRUNE_PROTECTED_TOKENS + 1,
    }
    monkeypatch.setattr(
        "app.agent_runtime.context.pruning.count_text_tokens",
        lambda content: sizes[content],
    )
    parts = _multi_turn_history(
        ("bash", "old"),
        ("activate_skill", "skill"),
        ("bash", "recent"),
        ("bash", "recent"),
    )

    result = prune_tool_outputs(parts)

    assert result[2].content == OLD_TOOL_OUTPUT_PLACEHOLDER
    assert result[5].content == "skill"
    assert result[8].content == "recent"
    assert result[11].content == "recent"


def test_preserves_subagent_coordination_outputs(monkeypatch) -> None:
    sizes = {
        "old": PRUNE_PROTECTED_TOKENS + PRUNE_MINIMUM_TOKENS + 1,
        "coordination": PRUNE_PROTECTED_TOKENS + 1,
        "recent": PRUNE_PROTECTED_TOKENS + 1,
    }
    monkeypatch.setattr(
        "app.agent_runtime.context.pruning.count_text_tokens",
        lambda content: sizes[content],
    )
    parts = _multi_turn_history(
        ("bash", "old"),
        ("dispatch_subagent", "coordination"),
        ("notify_subagent", "coordination"),
        ("bash", "recent"),
        ("bash", "recent"),
    )

    result = prune_tool_outputs(parts)

    assert result[2].content == OLD_TOOL_OUTPUT_PLACEHOLDER
    assert result[5].content == "coordination"
    assert result[8].content == "coordination"


def test_stops_at_an_already_pruned_tool_output(monkeypatch) -> None:
    sizes = {
        "old": PRUNE_PROTECTED_TOKENS + PRUNE_MINIMUM_TOKENS + 1,
        "recent": PRUNE_PROTECTED_TOKENS + 1,
    }
    monkeypatch.setattr(
        "app.agent_runtime.context.pruning.count_text_tokens",
        lambda content: sizes[content],
    )
    parts = _multi_turn_history(
        ("bash", "old"),
        ("bash", "old"),
        ("bash", "recent"),
        ("bash", "recent"),
    )
    parts[4] = _history(
        "tool",
        "old",
        seq=4,
        tool_call_id="call-2",
        name="bash",
        pruned=True,
    )

    result = prune_tool_outputs(parts)

    assert result[2].content == "old"
    assert result[5].content == OLD_TOOL_OUTPUT_PLACEHOLDER
    assert result[8].content == "recent"
    assert result[11].content == "recent"


def test_preserves_non_completed_tool_outputs(monkeypatch) -> None:
    sizes = {
        "old": PRUNE_PROTECTED_TOKENS + PRUNE_MINIMUM_TOKENS + 1,
        "recent": max(PRUNE_PROTECTED_TOKENS // 10, 1),
    }
    monkeypatch.setattr(
        "app.agent_runtime.context.pruning.count_text_tokens",
        lambda content: sizes[content],
    )
    parts = _multi_turn_history(
        ("bash", "old"),
        ("bash", "recent"),
        ("bash", "recent"),
        ("bash", "recent"),
    )
    parts[2] = _history(
        "tool",
        "old",
        seq=1,
        tool_call_id="call-1",
        name="bash",
        status="aborted",
    )

    result = prune_tool_outputs(parts)

    assert result == parts


def test_allows_pruning_after_two_completed_steps_in_one_user_turn(monkeypatch) -> None:
    sizes = {
        "old": PRUNE_PROTECTED_TOKENS + PRUNE_MINIMUM_TOKENS + 1,
        "recent": PRUNE_PROTECTED_TOKENS + 1,
    }
    monkeypatch.setattr(
        "app.agent_runtime.context.pruning.count_text_tokens",
        lambda content: sizes[content],
    )
    parts = [
        _history("user", "request", seq=0),
        *_step(1, "old"),
        *_step(2, "recent"),
        *_step(3, "recent"),
    ]

    result = prune_tool_outputs(parts)

    assert result[2].content == OLD_TOOL_OUTPUT_PLACEHOLDER
    assert result[4].content == "recent"
    assert result[6].content == "recent"
