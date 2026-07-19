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
    primary = get_default_agent_definition("primary")
    assert primary.delegatable_agents == (
        "explorer",
        "composer",
        "auditor",
        "writer",
        "actor",
        "reviewer",
    )

    for key in DEFAULT_AGENT_KEYS[1:]:
        definition = get_default_agent_definition(key)
        assert definition.key == key
        assert definition.prompt_agent_name == key
        assert definition.enabled is True
        assert definition.source == "builtin"
        assert definition.delegatable_agents == ()


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
                    enabled_tool_categories=["finish"],
                    enabled_skills=["skill-review"],
                    metadata_json={"scope": "custom"},
                    enabled=False,
                    order_index=10,
                )
            )
            await session.commit()

            definition = await load_agent_definition(session, "reviewer")

        assert definition.display_name == "Custom Reviewer"
        assert definition.model_id == "model-reviewer"
        assert definition.enabled_tool_categories == ("finish",)
        assert definition.enabled_skills == ("skill-review",)
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
                    enabled_tool_categories=["chapter_read"],
                    enabled_skills=["skill-custom"],
                    metadata_json={},
                    enabled=True,
                    source="custom",
                    delegatable_agents=["explorer"],
                )
            )
            await session.commit()

            definition = await load_agent_definition(session, "custom-bot")

        assert definition.source == "custom"
        assert definition.enabled_skills == ("skill-custom",)
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
                    enabled_tool_categories=["chapter_read"],
                    enabled_skills=[],
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
                    enabled_tool_categories=["chapter_read"],
                    enabled_skills=[],
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
