from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _definition(enabled_skills):
    return SimpleNamespace(enabled_skills=tuple(enabled_skills))


def _make_state():
    return {
        "session_id": "sess-1",
        "project_id": "proj-1",
        "model_config": {},
        "active_agent": "writer",
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "user_request": "",
    }


def _skill(id="skill-1", name="pdf-processing", summary="摘要", content="# PDF 内容", is_enabled=True):
    return SimpleNamespace(
        id=id,
        name=name,
        summary=summary,
        content=content,
        is_enabled=is_enabled,
    )


def _ref(title="参考文档1", content="参考内容1"):
    return SimpleNamespace(id="ref-1", title=title, content=content)


@pytest.mark.asyncio
async def test_skill_tool_names_for_definition_empty():
    from app.agent_runtime.tools.impls.skill.skill import (
        skill_tool_names_for_definition,
    )

    assert await skill_tool_names_for_definition(_definition([]), AsyncMock()) == ()


@pytest.mark.asyncio
async def test_skill_tool_names_for_definition_with_no_available():
    from app.agent_runtime.tools.impls.skill.skill import skill_tool_names_for_definition

    with patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_enabled_skills_by_ids",
        AsyncMock(return_value=[]),
    ):
        result = await skill_tool_names_for_definition(_definition(["skill-1"]), AsyncMock())
    assert result == ()


@pytest.mark.asyncio
async def test_skill_tool_names_for_definition_with_skills():
    from app.agent_runtime.tools.impls.skill.skill import skill_tool_names_for_definition

    with patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_enabled_skills_by_ids",
        AsyncMock(return_value=[_skill()]),
    ):
        result = await skill_tool_names_for_definition(_definition(["skill-1"]), AsyncMock())
    assert result == (
        "activate_skill",
        "reference_skill",
    )


def _patch_env(definition, skill, docs):
    def _list_by_ids(_session, _ids):
        return [skill]

    return [
        patch(
            "app.agent_runtime.tools.impls.skill.skill.load_agent_definition",
            AsyncMock(return_value=definition),
        ),
        patch(
            "app.agent_runtime.tools.impls.skill.skill.skill_service.list_enabled_skills_by_ids",
            AsyncMock(side_effect=_list_by_ids),
        ),
        patch(
            "app.agent_runtime.tools.impls.skill.skill.skill_service.list_reference_docs",
            AsyncMock(return_value=docs),
        ),
    ]


@pytest.mark.asyncio
async def test_activate_skill_returns_content_and_references():
    from app.agent_runtime.tools.impls.skill.skill import ActivateSkillTool

    tool = ActivateSkillTool(_state=_make_state())
    docs = [_ref()]
    patches = _patch_env(_definition(["skill-1"]), _skill(), docs)
    with patch(
        "app.agent_runtime.tools.impls.skill.skill.create_session",
        AsyncMock(return_value=AsyncMock()),
    ), patches[0], patches[1], patches[2]:
        result = await tool.ainvoke({"skill_name": "pdf-processing"})

    assert "<skill_content name=\"pdf-processing\">" in result
    assert "# PDF 内容" in result
    assert "<skill_references>" in result
    assert "<ref>参考文档1</ref>" in result


@pytest.mark.asyncio
async def test_activate_skill_no_references():
    from app.agent_runtime.tools.impls.skill.skill import ActivateSkillTool

    tool = ActivateSkillTool(_state=_make_state())
    patches = _patch_env(_definition(["skill-1"]), _skill(), [])
    with patch(
        "app.agent_runtime.tools.impls.skill.skill.create_session",
        AsyncMock(return_value=AsyncMock()),
    ), patches[0], patches[1], patches[2]:
        result = await tool.ainvoke({"skill_name": "pdf-processing"})

    assert "<skill_references>" not in result
    assert "<skill_content name=\"pdf-processing\">" in result


@pytest.mark.asyncio
async def test_builtin_skill_tools_read_content_and_references_from_yaml(monkeypatch):
    from app.agent_runtime.tools.impls.skill.skill import ActivateSkillTool, ReferenceSkillTool
    import app.storage.database as database
    import app.storage.services.skill_service as skill_service

    session = AsyncMock()
    monkeypatch.setattr(database, "create_session", AsyncMock(return_value=session))
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.skill.skill.create_session",
        AsyncMock(return_value=session),
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.skill.skill.load_agent_definition",
        AsyncMock(return_value=_definition(["builtin-skill--continue-chapter"])),
    )
    monkeypatch.setattr("app.storage.repos.skill_repo.list_by_ids", AsyncMock(return_value=[]))

    with patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_enabled_skills_by_ids",
        skill_service.list_enabled_skills_by_ids,
    ), patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_reference_docs",
        skill_service.list_reference_docs,
    ):
        activated = await ActivateSkillTool(_state=_make_state()).ainvoke({"skill_name": "章节续写"})
        referenced = await ReferenceSkillTool(_state=_make_state()).ainvoke(
            {"skill_name": "章节续写", "reference_name": "续写检查清单"}
        )

    assert "## 执行要求" in activated
    assert "<ref>续写检查清单</ref>" in activated
    assert "当前叙事视角是否与目标章节一致。" in referenced


@pytest.mark.asyncio
async def test_activate_skill_rejects_unauthorized_skill():
    import json

    from app.agent_runtime.tools.impls.skill.skill import ActivateSkillTool

    tool = ActivateSkillTool(_state=_make_state())
    with patch(
        "app.agent_runtime.tools.impls.skill.skill.load_agent_definition",
        AsyncMock(return_value=_definition(["other-id"])),
    ), patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_enabled_skills_by_ids",
        AsyncMock(return_value=[]),
    ), patch(
        "app.agent_runtime.tools.impls.skill.skill.create_session",
        AsyncMock(return_value=AsyncMock()),
    ):
        result = await tool.ainvoke({"skill_name": "pdf-processing"})

    assert "技能不在该智能体的可用列表中" in json.loads(result)["error"]


@pytest.mark.asyncio
async def test_activate_skill_rejects_disabled_skill():
    import json

    from app.agent_runtime.tools.impls.skill.skill import ActivateSkillTool

    tool = ActivateSkillTool(_state=_make_state())
    with patch(
        "app.agent_runtime.tools.impls.skill.skill.load_agent_definition",
        AsyncMock(return_value=_definition(["skill-1"])),
    ), patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_enabled_skills_by_ids",
        AsyncMock(return_value=[]),
    ), patch(
        "app.agent_runtime.tools.impls.skill.skill.create_session",
        AsyncMock(return_value=AsyncMock()),
    ):
        result = await tool.ainvoke({"skill_name": "pdf-processing"})

    assert "技能不在该智能体的可用列表中" in json.loads(result)["error"]


@pytest.mark.asyncio
async def test_reference_skill_returns_content():
    from app.agent_runtime.tools.impls.skill.skill import ReferenceSkillTool

    tool = ReferenceSkillTool(_state=_make_state())
    docs = [_ref("参考文档1", "参考内容1"), _ref("参考文档2", "参考内容2")]
    patches = _patch_env(_definition(["skill-1"]), _skill(), docs)
    with patch(
        "app.agent_runtime.tools.impls.skill.skill.create_session",
        AsyncMock(return_value=AsyncMock()),
    ), patches[0], patches[1], patches[2]:
        result = await tool.ainvoke(
            {"skill_name": "pdf-processing", "reference_name": "参考文档2"}
        )

    assert '<reference_content skill_name="pdf-processing" reference_name="参考文档2">' in result
    assert "参考内容2" in result


@pytest.mark.asyncio
async def test_reference_skill_rejects_unknown_reference():
    import json

    from app.agent_runtime.tools.impls.skill.skill import ReferenceSkillTool

    tool = ReferenceSkillTool(_state=_make_state())
    docs = [_ref("参考文档1", "参考内容1")]
    patches = _patch_env(_definition(["skill-1"]), _skill(), docs)
    with patch(
        "app.agent_runtime.tools.impls.skill.skill.create_session",
        AsyncMock(return_value=AsyncMock()),
    ), patches[0], patches[1], patches[2]:
        result = await tool.ainvoke(
            {"skill_name": "pdf-processing", "reference_name": "不存在"}
        )

    assert "参考文档不存在" in json.loads(result)["error"]
