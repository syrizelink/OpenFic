from app.prompts.loader import load_prompt_chain


ACTIVE_AGENT_NAMES = ("primary", "explorer", "composer", "auditor", "writer", "actor", "reviewer")
REMOVED_AGENT_NAMES = ("clarifier", "planner", "collector", "yolo", "designer")


def _content(agent_name: str) -> str:
    entries = load_prompt_chain("assistant", "agent", agent_name)
    assert entries is not None, f"missing default prompt chain for {agent_name}"
    return "\n".join(entry.content for entry in entries)


def test_active_pa_sa_agents_have_default_prompt_chains() -> None:
    for agent_name in ACTIVE_AGENT_NAMES:
        assert _content(agent_name)


def test_removed_agent_identities_have_no_default_prompt_chains() -> None:
    for agent_name in REMOVED_AGENT_NAMES:
        assert load_prompt_chain("assistant", "agent", agent_name) is None


def test_reviewer_prompt_returns_plain_text_review_contract() -> None:
    content = _content("reviewer")

    assert "review" in content or "审核" in content
    assert "普通 assistant 文本" in content or "普通文本" in content


def test_compaction_prompt_has_enabled_system_entry() -> None:
    entries = load_prompt_chain("assistant", "compaction", None)

    assert entries is not None
    assert any(entry.role == "system" and entry.is_enabled for entry in entries)
