from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import pytest
from app.agent_runtime.context.parts.skills import build_skills


def _skill(name: str, summary: str, content: str = ""):
    return SimpleNamespace(id=name, name=name, summary=summary, content=content)


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


@pytest.mark.asyncio
async def test_skills_appends_referenced_global_skill_after_agent_skills(make_state, mock_session):
    state = make_state(user_request="请继续")
    agent_skill = SimpleNamespace(
        id="agent-skill",
        name="agent-skill",
        summary="默认技能",
        content="内容",
    )
    referenced_skill = SimpleNamespace(
        id="global-skill-id",
        name="global-skill",
        summary="显式引用技能",
        content="内容",
    )

    async def list_by_ids(_session, ids):
        return [agent_skill] if ids == ["agent-skill"] else []

    with patch(
        "app.agent_runtime.context.parts.skills._get_enabled_skill_ids_for_agent",
        AsyncMock(return_value=["agent-skill"]),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills_by_ids",
        AsyncMock(side_effect=list_by_ids),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills",
        AsyncMock(return_value=[agent_skill, referenced_skill]),
        create=True,
    ):
        msg = await build_skills(
            state,
            "writer",
            mock_session,
            [
                {
                    "role": "user",
                    "content": '<of-skill id="global-skill-id" name="global-skill" />',
                }
            ],
        )

    assert msg is not None
    assert msg.content.index("<name>agent-skill</name>") < msg.content.index(
        "<name>global-skill</name>"
    )


@pytest.mark.asyncio
async def test_skills_does_not_append_disabled_referenced_skill(make_state, mock_session):
    state = make_state(user_request="请继续")
    agent_skill = _skill("agent-skill", "默认技能", "内容")

    with patch(
        "app.agent_runtime.context.parts.skills._get_enabled_skill_ids_for_agent",
        AsyncMock(return_value=["agent-skill"]),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills_by_ids",
        AsyncMock(return_value=[agent_skill]),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills",
        AsyncMock(return_value=[agent_skill]),
        create=True,
    ):
        msg = await build_skills(
            state,
            "writer",
            mock_session,
            [
                {
                    "role": "user",
                    "content": '<of-skill id="disabled-skill-id" name="disabled-skill" />',
                }
            ],
        )

    assert msg is not None
    assert "<name>disabled-skill</name>" not in msg.content


@pytest.mark.asyncio
async def test_skills_escapes_xml_fields(make_state, mock_session):
    state = make_state()
    unsafe_skill = _skill("skill & <name>", '描述 & <指令> "quoted"', "内容")

    with patch(
        "app.agent_runtime.context.parts.skills._get_enabled_skill_ids_for_agent",
        AsyncMock(return_value=[unsafe_skill.id]),
    ), patch(
        "app.agent_runtime.context.parts.skills.skill_service.list_enabled_skills_by_ids",
        AsyncMock(return_value=[unsafe_skill]),
    ):
        msg = await build_skills(state, "writer", mock_session)

    assert msg is not None
    assert "skill &amp; &lt;name&gt;" in msg.content
    assert "描述 &amp; &lt;指令&gt; &quot;quoted&quot;" in msg.content
