from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import pytest
from app.agent_runtime.context.parts.skills import build_skills


def _skill(skill_id: str, name: str, summary: str, content: str = ""):
    return SimpleNamespace(skill_id=skill_id, name=name, summary=summary, content=content)


@pytest.mark.asyncio
async def test_skills_returns_none_for_unknown_agent(make_state, mock_session):
    state = make_state()
    with patch(
        "app.agent_runtime.context.parts.skills._get_enabled_skill_ids_for_agent",
        AsyncMock(return_value=[]),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills_by_skill_ids",
        AsyncMock(return_value=[]),
    ):
        msg = await build_skills(state, "unknown", mock_session)
    assert msg is None


@pytest.mark.asyncio
async def test_skills_returns_none_when_no_skills(make_state, mock_session):
    state = make_state(installed_skill_ids=[])
    with patch(
        "app.agent_runtime.context.parts.skills._get_enabled_skill_ids_for_agent",
        AsyncMock(return_value=[]),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills_by_skill_ids",
        AsyncMock(return_value=[]),
    ):
        msg = await build_skills(state, "writer", mock_session)
    assert msg is None


@pytest.mark.asyncio
async def test_skills_renders_available_only(make_state, mock_session):
    state = make_state(installed_skill_ids=[])
    available = [
        _skill("s1", "技能一", "做什么的"),
        _skill("s2", "技能二", "另一个"),
    ]
    with patch(
        "app.agent_runtime.context.parts.skills._get_enabled_skill_ids_for_agent",
        AsyncMock(return_value=["s1", "s2"]),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills_by_skill_ids",
        AsyncMock(return_value=available),
    ):
        msg = await build_skills(state, "writer", mock_session)
    assert msg is not None
    assert msg.metadata == {"part": "skills"}
    assert "<skills>" in msg.content
    assert "## 可用技能" in msg.content
    assert "`s1` — 技能一：做什么的" in msg.content
    assert "`s2` — 技能二：另一个" in msg.content
    assert "## 已激活技能" not in msg.content


@pytest.mark.asyncio
async def test_skills_renders_installed_with_content(make_state, mock_session):
    state = make_state(installed_skill_ids=["s1"])
    available = [_skill("s1", "技能一", "摘要"), _skill("s2", "技能二", "其它")]
    installed = [_skill("s1", "技能一", "摘要", content="完整内容")]
    with patch(
        "app.agent_runtime.context.parts.skills._get_enabled_skill_ids_for_agent",
        AsyncMock(return_value=["s1", "s2"]),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills_by_skill_ids",
        AsyncMock(return_value=available),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_skills_by_skill_ids",
        AsyncMock(return_value=installed),
    ):
        msg = await build_skills(state, "writer", mock_session)
    assert msg is not None
    assert "## 已激活技能" in msg.content
    assert "### s1 技能一" in msg.content
    assert "完整内容" in msg.content
