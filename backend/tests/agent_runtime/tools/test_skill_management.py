import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.agents.definitions import get_default_agent_definition
from app.agent_runtime.agents.tool_categories import (
    get_tool_names_for_categories,
    list_tool_categories,
)
from app.agent_runtime.persistence.model import AgentDefinitionRecord
from app.agent_runtime.tools import ToolRegistry
from app.agent_runtime.tools.base import HookContext
from app.agent_runtime.tools.impls.skill import manage
from app.skills import load_builtin_skills
from app.storage.models.skill import Skill
from app.storage.models.skill_reference_doc import SkillReferenceDoc


@pytest.fixture
async def tools_with_database(session: AsyncSession, monkeypatch):
    connection = await session.connection()

    async def create_session():
        return AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

    monkeypatch.setattr(manage, "create_session", create_session)

    async def invoke(tool_name, **kwargs):
        tool = ToolRegistry.get_tools(names=[tool_name], state={})[0]
        return json.loads(await tool.ainvoke(kwargs))

    return invoke


async def test_create_edit_and_list_skill_and_reference(session, tools_with_database):
    agent = AgentDefinitionRecord(
        key="custom-test",
        display_name="Test",
        kind="primary",
        prompt_agent_name="build",
        enabled_skills=["existing-skill"],
    )
    session.add(agent)
    await session.flush()

    created = await tools_with_database(
        "create_skill", name="Draft", summary="Summary", content="Original content"
    )
    skill = created["skill"]
    skill_id = skill["id"]
    assert created["success"] is True
    assert created["metadata"]["skill_diff"]["skill_name"] == "Draft"
    assert {
        section["type"] for section in created["metadata"]["skill_diff"]["sections"]
    } == {"name", "summary", "content"}
    assert skill["is_enabled"] is False
    assert skill["reference_docs"] == []
    assert not (await session.execute(select(SkillReferenceDoc))).scalars().all()
    await session.refresh(agent)
    assert agent.enabled_skills == ["existing-skill"]

    ref = await tools_with_database(
        "create_skill_reference_doc",
        skill_id=skill_id,
        title="Guide",
        content="First version",
    )
    doc_id = ref["reference_doc"]["id"]
    assert ref["reference_doc"]["tokens"] > 0
    assert ref["metadata"]["skill_diff"]["reference_doc_title"] == "Guide"
    assert {
        section["type"] for section in ref["metadata"]["skill_diff"]["sections"]
    } == {"title", "content"}
    edited = await tools_with_database(
        "edit_skill", skill_id=skill_id, name="Updated", content="Updated content"
    )
    assert edited["skill"]["is_enabled"] is False
    assert edited["skill"]["summary"] == "Summary"
    assert edited["metadata"]["skill_diff"]["skill_name"] == "Updated"
    sections = {
        section["type"]: section
        for section in edited["metadata"]["skill_diff"]["sections"]
    }
    assert set(sections) == {"name", "content"}
    assert [(line["type"], line["text"]) for line in sections["content"]["lines"]] == [
        ("removed", "Original content"),
        ("added", "Updated content"),
    ]
    updated_ref = await tools_with_database(
        "edit_skill_reference_doc",
        skill_id=skill_id,
        doc_id=doc_id,
        title="Updated guide",
        content="Updated reference",
    )
    assert updated_ref["reference_doc"]["content"] == "Updated reference"
    assert (
        updated_ref["metadata"]["skill_diff"]["reference_doc_title"] == "Updated guide"
    )
    assert {
        section["type"] for section in updated_ref["metadata"]["skill_diff"]["sections"]
    } == {"title", "content"}
    listed = await tools_with_database("list_skills")
    item = next(item for item in listed["skills"] if item["id"] == skill_id)
    assert item["name"] == "Updated"
    assert item["content"] == "Updated content"
    assert item["reference_docs"][0]["id"] == doc_id
    assert item["reference_docs"][0]["content"] == "Updated reference"
    assert any(item["source"] == "builtin" for item in listed["skills"])


async def test_skill_diff_uses_persisted_values_and_omits_unchanged_fields(
    session,
    tools_with_database,
):
    skill = Skill(name="Original", summary="Old summary", content="Content")
    session.add(skill)
    await session.flush()
    skill_id = skill.id
    unchanged = await tools_with_database(
        "edit_skill", skill_id=skill_id, name=" Original "
    )
    assert unchanged["metadata"]["skill_diff"]["sections"] == []

    changed = await tools_with_database(
        "edit_skill", skill_id=skill_id, summary=" New summary "
    )
    sections = changed["metadata"]["skill_diff"]["sections"]
    assert len(sections) == 1
    assert sections[0]["type"] == "summary"
    assert [(line["type"], line["text"]) for line in sections[0]["lines"]] == [
        ("removed", "Old summary"),
        ("added", "New summary"),
    ]


async def test_create_and_rename_ignore_invalid_legacy_skill_names(
    session, tools_with_database
):
    session.add(
        Skill(
            id="legacy-invalid-name",
            name="legacy\nname",
            summary="Old summary",
            content="Old content",
        )
    )
    await session.flush()

    created = await tools_with_database(
        "create_skill", name="Valid name", summary="Summary", content="Content"
    )
    assert created["success"] is True

    renamed = await tools_with_database(
        "edit_skill", skill_id="legacy-invalid-name", name="Renamed"
    )
    assert renamed["success"] is True
    assert renamed["skill"]["name"] == "Renamed"


async def test_delete_skill_and_reference_doc(session, tools_with_database):
    created = await tools_with_database(
        "create_skill", name="To delete", summary="Summary", content="Content"
    )
    skill_id = created["skill"]["id"]
    reference = await tools_with_database(
        "create_skill_reference_doc",
        skill_id=skill_id,
        title="Guide",
        content="Reference",
    )

    deleted_doc = await tools_with_database(
        "delete_skill_reference_doc",
        skill_id=skill_id,
        doc_id=reference["reference_doc"]["id"],
    )
    assert deleted_doc["success"] is True
    assert deleted_doc["metadata"]["skill_diff"]["reference_doc_title"] == "Guide"
    assert deleted_doc["metadata"]["skill_diff"]["operation"] == "delete"
    assert all(
        line["type"] == "removed"
        for section in deleted_doc["metadata"]["skill_diff"]["sections"]
        for line in section["lines"]
    )

    await tools_with_database(
        "create_skill_reference_doc",
        skill_id=skill_id,
        title="Other",
        content="Other reference",
    )

    deleted_skill = await tools_with_database("delete_skill", skill_id=skill_id)
    assert deleted_skill["success"] is True
    assert deleted_skill["metadata"]["skill_diff"]["skill_name"] == "To delete"
    sections = deleted_skill["metadata"]["skill_diff"]["sections"]
    assert any(section.get("reference_doc_title") == "Other" for section in sections)
    assert all(
        line["type"] == "removed" for section in sections for line in section["lines"]
    )


async def test_skill_tools_reject_internal_tabs_without_persisting(
    session, tools_with_database
):
    created = await tools_with_database(
        "create_skill", name="制表\t符名", summary="Summary", content="Content"
    )
    assert created["success"] is False
    assert created["code"] == "validation_error"
    assert created["message"] == "Skill 名称不能包含换行符或制表符。"
    assert not (await session.execute(select(Skill))).scalars().all()

    skill = Skill(
        id="tab-rename-skill",
        name="Original",
        summary="Summary",
        content="Content",
    )
    session.add(skill)
    await session.flush()
    renamed = await tools_with_database(
        "edit_skill", skill_id=skill.id, name="改名带\t制表"
    )
    assert renamed["success"] is False
    assert renamed["code"] == "validation_error"
    assert renamed["message"] == "Skill 名称不能包含换行符或制表符。"
    await session.refresh(skill)
    assert skill.name == "Original"


async def test_list_includes_all_pages_and_enabled_and_disabled_skills(
    session, tools_with_database
):
    session.add_all(
        [
            Skill(
                id=f"custom-{i:03}",
                name=f"Skill {i}",
                summary="S",
                content="C",
                is_enabled=i % 2 == 0,
            )
            for i in range(110)
        ]
    )
    await session.flush()
    listed = await tools_with_database("list_skills")
    custom = {
        item["id"]: item for item in listed["skills"] if item["source"] == "custom"
    }
    assert len(custom) == 110
    assert listed["total"] == 110 + len(load_builtin_skills())
    assert custom["custom-000"]["is_enabled"] is True
    assert custom["custom-109"]["is_enabled"] is False
    assert "content" not in custom["custom-000"]
    assert "reference_docs" not in custom["custom-000"]
    assert custom["custom-109"]["content"] == "C"


async def test_enabled_and_builtin_skills_cannot_be_changed(
    session, tools_with_database
):
    enabled = Skill(
        id="enabled", name="Enabled", summary="S", content="Original", is_enabled=True
    )
    doc = SkillReferenceDoc(
        id="enabled-doc", skill_db_id=enabled.id, title="Old", content="Old"
    )
    session.add_all([enabled, doc])
    await session.flush()
    for name, args in (
        ("edit_skill", {"skill_id": enabled.id, "content": "Changed"}),
        (
            "create_skill_reference_doc",
            {"skill_id": enabled.id, "title": "New", "content": "New"},
        ),
        (
            "edit_skill_reference_doc",
            {"skill_id": enabled.id, "doc_id": doc.id, "content": "Changed"},
        ),
    ):
        result = await tools_with_database(name, **args)
        assert result["code"] == "permission_denied"
        assert "已启用" in result["message"]

    # Built-ins remain immutable even when their global enabled override is off.
    builtin = load_builtin_skills()[0]
    session.add(Skill(id=builtin.id, is_enabled=False))
    await session.flush()
    for name, args in (
        ("edit_skill", {"skill_id": builtin.id, "content": "Changed"}),
        (
            "create_skill_reference_doc",
            {"skill_id": builtin.id, "title": "New", "content": "New"},
        ),
        (
            "edit_skill_reference_doc",
            {"skill_id": builtin.id, "doc_id": "anything", "content": "Changed"},
        ),
    ):
        result = await tools_with_database(name, **args)
        assert result["code"] == "permission_denied"
        assert "内置" in result["message"]
    await session.refresh(enabled)
    await session.refresh(doc)
    assert enabled.content == "Original" and enabled.is_enabled is True
    assert doc.content == "Old"
    assert len((await session.execute(select(SkillReferenceDoc))).scalars().all()) == 1


async def test_switch_and_reference_arguments_are_rejected_and_doc_ownership_checked(
    session, tools_with_database
):
    session.add_all(
        [
            Skill(id="a", name="A", summary="S", content="C"),
            Skill(id="b", name="B", summary="S", content="C"),
            SkillReferenceDoc(
                id="doc-b", skill_db_id="b", title="B", content="Original"
            ),
        ]
    )
    await session.flush()
    for name, args in (
        (
            "create_skill",
            {"name": "X", "summary": "S", "content": "C", "is_enabled": True},
        ),
        (
            "create_skill",
            {"name": "X", "summary": "S", "content": "C", "references": []},
        ),
        ("edit_skill", {"skill_id": "a", "name": "New", "is_enabled": True}),
    ):
        result = await tools_with_database(name, **args)
        assert result["code"] == "validation_error"
    result = await tools_with_database(
        "edit_skill_reference_doc", skill_id="a", doc_id="doc-b", content="Changed"
    )
    assert result["code"] == "not_found"
    result = await tools_with_database(
        "edit_skill", skill_id="missing", content="Changed"
    )
    assert result["code"] == "not_found"
    doc = await session.get(SkillReferenceDoc, "doc-b")
    assert doc.content == "Original"


async def test_edit_rechecks_enabled_status_when_locking_row(
    session, tools_with_database, monkeypatch
):
    skill = Skill(
        id="changed", name="Changed", summary="S", content="Original", is_enabled=True
    )
    session.add(skill)
    await session.flush()

    async def stale_disabled_view(*args):
        return SimpleNamespace(source="custom", is_enabled=False)

    monkeypatch.setattr(manage.skill_service, "get_skill", stale_disabled_view)
    result = await tools_with_database(
        "edit_skill", skill_id=skill.id, content="Changed"
    )
    assert result["code"] == "permission_denied"
    await session.refresh(skill)
    assert skill.is_enabled is True
    assert skill.content == "Original"


def test_skill_management_available_to_default_build_and_registered():
    assert next(name for key, name, _ in list_tool_categories() if key == "skill_management") == "技能管理"
    names = set(get_tool_names_for_categories(["skill_management"]))
    assert names == {
        "list_skills",
        "create_skill",
        "edit_skill",
        "create_skill_reference_doc",
        "edit_skill_reference_doc",
        "delete_skill",
        "delete_skill_reference_doc",
        "get_skill",
        "get_skill_reference_doc",
    }
    assert names <= set(ToolRegistry.list_names())
    assert (
        "skill_management"
        in get_default_agent_definition("build").enabled_tool_categories
    )


async def test_skill_refresh_notifies_parent_only_after_success(monkeypatch):
    from app.agent_runtime.tools.hooks.skill_refresh import skill_refresh_post_hook

    events = []

    async def fake_emit(event, data, *, room=None):
        events.append((event, data, room))

    monkeypatch.setattr("app.agent_runtime.tools.hooks.skill_refresh.emit", fake_emit)
    context = HookContext(
        tool_name="edit_skill_reference_doc",
        access_level="write",
        args={},
        state={"session_id": "child", "parent_session_id": "parent"},
        output=json.dumps({"success": True, "skill_id": "skill-1"}),
    )
    await skill_refresh_post_hook(context)
    assert events[0][0] == "agent:skill_refresh"
    assert events[0][1]["skill_id"] == "skill-1"
    assert events[0][1]["session_id"] == "parent"
    context.output = json.dumps({"success": False})
    await skill_refresh_post_hook(context)
    assert len(events) == 1
