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


@pytest.mark.asyncio
async def test_skill_tool_names_for_definition_with_explicit_reference():
    from app.agent_runtime.tools.impls.skill.skill import skill_tool_names_for_definition

    with patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_enabled_skills_by_ids",
        AsyncMock(return_value=[]),
    ), patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_enabled_skills",
        AsyncMock(return_value=[_skill(id="skill-explicit", name="显式引用技能")]),
        create=True,
    ):
        result = await skill_tool_names_for_definition(
            _definition([]),
            AsyncMock(),
            referenced_skill_ids=["skill-explicit"],
        )

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
    from app.skills import load_builtin_skills
    import app.storage.database as database
    import app.storage.services.skill_service as skill_service

    builtin_skill = next(
        skill
        for skill in load_builtin_skills()
        if skill.is_enabled and skill.references
    )
    reference = builtin_skill.references[0]
    session = AsyncMock()
    monkeypatch.setattr(database, "create_session", AsyncMock(return_value=session))
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.skill.skill.create_session",
        AsyncMock(return_value=session),
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.skill.skill.load_agent_definition",
        AsyncMock(return_value=_definition([builtin_skill.id])),
    )
    monkeypatch.setattr("app.storage.repos.skill_repo.list_by_ids", AsyncMock(return_value=[]))

    with patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_enabled_skills_by_ids",
        skill_service.list_enabled_skills_by_ids,
    ), patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_reference_docs",
        skill_service.list_reference_docs,
    ):
        activated = await ActivateSkillTool(_state=_make_state()).ainvoke(
            {"skill_name": builtin_skill.name}
        )
        referenced = await ReferenceSkillTool(_state=_make_state()).ainvoke(
            {"skill_name": builtin_skill.name, "reference_name": reference.title}
        )

    assert builtin_skill.content.strip() in activated
    assert f"<ref>{reference.title}</ref>" in activated
    assert reference.content.strip() in referenced


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
async def test_activate_skill_accepts_explicitly_referenced_global_skill():
    from app.agent_runtime.tools.impls.skill.skill import _resolve_authorized_skill

    skill = _skill(id="skill-explicit", name="显式引用技能")
    state = _make_state()
    state["referenced_skill_ids"] = [skill.id]
    session = AsyncMock()

    with patch(
        "app.agent_runtime.tools.impls.skill.skill.load_agent_definition",
        AsyncMock(return_value=_definition([])),
    ), patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_enabled_skills_by_ids",
        AsyncMock(return_value=[]),
    ), patch(
        "app.agent_runtime.tools.impls.skill.skill.skill_service.list_enabled_skills",
        AsyncMock(return_value=[skill]),
        create=True,
    ):
        resolved = await _resolve_authorized_skill(session, state, skill.name)

    assert resolved is skill


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


def test_load_builtin_skills_caches_until_skill_files_change(tmp_path, monkeypatch):
    import app.skills.loader as loader

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "skill-a.yaml").write_text("placeholder", encoding="utf-8")
    (skills_dir / "skill-b.yaml").write_text("placeholder", encoding="utf-8")

    loaded: list[str] = []

    def fake_load(yaml_path):
        loaded.append(yaml_path.name)
        return SimpleNamespace(
            id=f"builtin-skill--{yaml_path.stem}",
            name=yaml_path.stem,
            summary="s",
            content="c",
            is_enabled=True,
            references=(),
            created_at=None,
            updated_at=None,
            source="builtin",
        )

    monkeypatch.setattr(loader, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(loader, "_load_builtin_skill", fake_load)
    monkeypatch.setattr(loader, "_skills_cache", None)

    first = loader.load_builtin_skills()
    assert [skill.id for skill in first] == [
        "builtin-skill--skill-a",
        "builtin-skill--skill-b",
    ]
    assert loaded == ["skill-a.yaml", "skill-b.yaml"]

    # 命中缓存，不再重新读取 YAML
    second = loader.load_builtin_skills()
    assert second == first
    assert loaded == ["skill-a.yaml", "skill-b.yaml"]

    # load_builtin_skill 复用缓存
    skill = loader.load_builtin_skill("builtin-skill--skill-a")
    assert skill is not None and skill.name == "skill-a"
    assert len(loaded) == 2

    # 修改文件内容使指纹变化，缓存失效后重新加载
    (skills_dir / "skill-b.yaml").write_text("placeholder-longer", encoding="utf-8")
    loader.load_builtin_skills()
    assert len(loaded) == 4
