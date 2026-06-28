import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel


def test_default_agent_definitions_include_primary_and_six_subagents():
    from app.agent_runtime.agents.definitions import (
        DEFAULT_AGENT_KEYS,
        get_default_agent_definition,
    )

    assert DEFAULT_AGENT_KEYS == (
        "primary",
        "explorer",
        "composer",
        "auditor",
        "writer",
        "actor",
        "reviewer",
    )
    for key in DEFAULT_AGENT_KEYS:
        definition = get_default_agent_definition(key)
        assert definition.key == key
        assert definition.prompt_agent_name == key
        assert definition.enabled is True
        assert definition.source == "builtin"
        assert definition.delegatable_agents == ()


def test_primary_can_dispatch_but_subagents_cannot():
    from app.agent_runtime.agents.definitions import get_default_agent_definition

    assert "orchestration" in get_default_agent_definition("primary").tool_category_keys
    for key in ("explorer", "composer", "auditor", "writer", "actor", "reviewer"):
        assert (
            "orchestration" not in get_default_agent_definition(key).tool_category_keys
        )


def test_writer_gets_mutation_category_and_reviewers_do_not():
    from app.agent_runtime.agents.definitions import get_default_agent_definition

    assert "chapter_write" in get_default_agent_definition("writer").tool_category_keys
    assert "chapter_write" in get_default_agent_definition("actor").tool_category_keys
    for key in ("explorer", "composer", "auditor", "reviewer"):
        assert (
            "chapter_write" not in get_default_agent_definition(key).tool_category_keys
        )


def test_note_category_allocation_matches_read_write_policy():
    from app.agent_runtime.agents.definitions import get_default_agent_definition

    for key in ("explorer", "composer", "auditor"):
        assert "note_read" in get_default_agent_definition(key).tool_category_keys
        assert "note_write" not in get_default_agent_definition(key).tool_category_keys

    for key in ("primary", "writer", "actor"):
        assert "note_read" in get_default_agent_definition(key).tool_category_keys
        assert "note_write" in get_default_agent_definition(key).tool_category_keys

    assert (
        "note_read" not in get_default_agent_definition("reviewer").tool_category_keys
    )
    assert (
        "note_write" not in get_default_agent_definition("reviewer").tool_category_keys
    )


@pytest.mark.asyncio
async def test_load_agent_definition_prefers_db_record():
    from app.agent_runtime.agents.definitions import load_agent_definition
    from app.agent_runtime.persistence.model import AgentDefinitionRecord

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            session.add(
                AgentDefinitionRecord(
                    key="reviewer",
                    display_name="Custom Reviewer",
                    kind="subagent",
                    prompt_agent_name="reviewer",
                    model_id="model-reviewer",
                    tool_category_keys_json=["finish"],
                    enabled_skill_ids_json=["skill-review"],
                    metadata_json={"scope": "custom"},
                    enabled=False,
                    order_index=10,
                )
            )
            await session.commit()

            definition = await load_agent_definition(session, "reviewer")

        assert definition.display_name == "Custom Reviewer"
        assert definition.model_id == "model-reviewer"
        assert definition.tool_category_keys == ("finish",)
        assert definition.enabled_skill_ids == ("skill-review",)
        assert definition.metadata == {"scope": "custom"}
        assert definition.enabled is False
        assert definition.source == "builtin"
        assert definition.delegatable_agents == ()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_load_custom_agent_definition_has_source_custom():
    from app.agent_runtime.agents.definitions import load_agent_definition
    from app.agent_runtime.persistence.model import AgentDefinitionRecord

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            session.add(
                AgentDefinitionRecord(
                    key="custom-bot",
                    display_name="Custom Bot",
                    kind="subagent",
                    prompt_agent_name="custom-bot",
                    model_id=None,
                    tool_category_keys_json=["chapter_read"],
                    enabled_skill_ids_json=["skill-custom"],
                    metadata_json={},
                    enabled=True,
                    source="custom",
                    delegatable_agents=["explorer"],
                )
            )
            await session.commit()

            definition = await load_agent_definition(session, "custom-bot")

        assert definition.source == "custom"
        assert definition.enabled_skill_ids == ("skill-custom",)
        assert definition.delegatable_agents == ("explorer",)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_load_agent_definition_falls_back_to_default_when_db_row_missing():
    from app.agent_runtime.agents.definitions import (
        get_default_agent_definition,
        load_agent_definition,
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            definition = await load_agent_definition(session, "explorer")

        assert definition == get_default_agent_definition("explorer")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_load_all_agent_definitions_merges_defaults_and_db_overrides():
    from app.agent_runtime.agents.definitions import load_all_agent_definitions
    from app.agent_runtime.persistence.model import AgentDefinitionRecord

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            session.add(
                AgentDefinitionRecord(
                    key="explorer",
                    display_name="Custom Explorer",
                    kind="subagent",
                    prompt_agent_name="explorer",
                    model_id=None,
                    tool_category_keys_json=["chapter_read"],
                    enabled_skill_ids_json=[],
                    metadata_json={},
                    enabled=False,
                    order_index=1,
                )
            )
            session.add(
                AgentDefinitionRecord(
                    key="custom-bot",
                    display_name="Custom Bot",
                    kind="subagent",
                    prompt_agent_name="custom-bot",
                    model_id=None,
                    tool_category_keys_json=["chapter_read"],
                    enabled_skill_ids_json=[],
                    metadata_json={},
                    enabled=True,
                    source="custom",
                    order_index=99,
                )
            )
            await session.commit()

            definitions = await load_all_agent_definitions(session)

        assert "primary" in definitions
        assert definitions["explorer"].display_name == "Custom Explorer"
        assert definitions["explorer"].enabled is False
        assert definitions["custom-bot"].source == "custom"
    finally:
        await engine.dispose()
