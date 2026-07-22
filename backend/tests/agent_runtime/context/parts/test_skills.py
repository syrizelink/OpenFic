from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import pytest
from app.agent_runtime.context.parts.skills import build_skills


def _skill(name: str, summary: str, content: str = ""):
    return SimpleNamespace(name=name, summary=summary, content=content)


@pytest.mark.asyncio
async def test_skills_returns_none_for_unknown_agent(make_state, mock_session):
    state = make_state()
    with patch(
        "app.agent_runtime.context.parts.skills._get_enabled_skill_ids_for_agent",
        AsyncMock(return_value=[]),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills_by_ids",
        AsyncMock(return_value=[]),
    ):
        msg = await build_skills(state, "unknown", mock_session)
    assert msg is None


@pytest.mark.asyncio
async def test_skills_returns_none_when_no_skills(make_state, mock_session):
    state = make_state()
    with patch(
        "app.agent_runtime.context.parts.skills._get_enabled_skill_ids_for_agent",
        AsyncMock(return_value=[]),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills_by_ids",
        AsyncMock(return_value=[]),
    ):
        msg = await build_skills(state, "writer", mock_session)
    assert msg is None


@pytest.mark.asyncio
async def test_skills_renders_available_xml(make_state, mock_session):
    state = make_state()
    available = [
        _skill("pdf-processing", "Extract PDF text, fill forms, merge files."),
        _skill("data-analysis", "Analyze datasets, generate charts."),
    ]
    with patch(
        "app.agent_runtime.context.parts.skills._get_enabled_skill_ids_for_agent",
        AsyncMock(return_value=["skill-pdf", "skill-data"]),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills_by_ids",
        AsyncMock(return_value=available),
    ):
        msg = await build_skills(state, "writer", mock_session)
    assert msg is not None
    assert msg.metadata == {"part": "skills"}
    assert msg.content.startswith("<available_skills>")
    assert msg.content.endswith("</available_skills>")
    assert "<name>pdf-processing</name>" in msg.content
    assert "<description>Extract PDF text, fill forms, merge files.</description>" in msg.content
    assert "<name>data-analysis</name>" in msg.content
    assert "<skill>" in msg.content
