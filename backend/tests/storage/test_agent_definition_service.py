# -*- coding: utf-8 -*-
"""Agent Definition Service 测试。"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.core.errors import NotFoundError, ValidationError


@pytest.mark.asyncio
async def test_list_definitions_includes_builtins():
    from app.storage.services import agent_definition_service

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            defs = await agent_definition_service.list_definitions(session)
            keys = {d.key for d in defs}

        assert "explorer" in keys
        assert "writer" in keys
        assert any(d.kind == "primary" for d in defs)
        assert all(d.source == "builtin" for d in defs if d.key in (
            "orchestrator", "explorer", "composer", "auditor", "writer", "actor", "reviewer"
        ))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_custom_definition():
    from app.storage.services import agent_definition_service

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            record = await agent_definition_service.create_definition(
                session,
                key="custom-bot",
                display_name="Custom Bot",
                description="Custom description",
                kind="subagent",
                prompt_agent_name="custom-bot",
                model_id=None,
                enabled_tool_categories=["chapter_read"],
                enabled_skills=["skill-a", "skill-b"],
                metadata={},
                delegatable_agents=[],
            )
            await session.commit()

            assert record.key == "custom-bot"
            assert record.source == "custom"
            assert record.description == "Custom description"
            assert record.enabled_skills == ["skill-a", "skill-b"]
            assert record.delegatable_agents == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_duplicate_raises_validation_error():
    from app.storage.services import agent_definition_service

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            await agent_definition_service.create_definition(
                session,
                key="dup",
                display_name="Dup",
                description="",
                kind="subagent",
                prompt_agent_name="dup",
                model_id=None,
                enabled_tool_categories=[],
                enabled_skills=[],
                metadata={},
                delegatable_agents=[],
            )
            await session.commit()

            with pytest.raises(ValidationError, match="已存在"):
                await agent_definition_service.create_definition(
                    session,
                    key="dup",
                    display_name="Dup2",
                    description="",
                    kind="subagent",
                    prompt_agent_name="dup2",
                    model_id=None,
                    enabled_tool_categories=[],
                    enabled_skills=[],
                    metadata={},
                    delegatable_agents=[],
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_custom_definition():
    from app.storage.services import agent_definition_service

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            await agent_definition_service.create_definition(
                session,
                key="edit-me",
                display_name="Edit Me",
                description="Before update",
                kind="subagent",
                prompt_agent_name="edit-me",
                model_id=None,
                enabled_tool_categories=[],
                enabled_skills=[],
                metadata={},
                delegatable_agents=[],
            )
            await session.commit()

            record = await agent_definition_service.update_definition(
                session,
                key="edit-me",
                display_name="Edited",
                description="After update",
                enabled_skills=["skill-c"],
                delegatable_agents=["explorer", "writer"],
            )
            await session.commit()

            assert record.display_name == "Edited"
            assert record.description == "After update"
            assert record.enabled_skills == ["skill-c"]
            assert record.delegatable_agents == ["explorer", "writer"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_update_builtin_creates_override_row():
    from app.storage.services import agent_definition_service
    from app.storage.repos import agent_definition_repo

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            record = await agent_definition_service.update_definition(
                session,
                key="reviewer",
                display_name="Custom Reviewer",
                description="Custom reviewer description",
                enabled=False,
            )
            await session.commit()

            assert record.key == "reviewer"
            assert record.display_name == "Custom Reviewer"
            assert record.description == "Custom reviewer description"
            assert record.source == "builtin"
            assert record.enabled is False

            db_record = await agent_definition_repo.get_by_key(session, "reviewer")
            assert db_record is not None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reset_builtin_removes_override():
    from app.storage.services import agent_definition_service
    from app.storage.repos import agent_definition_repo
    from app.agent_runtime.agents.definitions import get_default_agent_definition

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            await agent_definition_service.update_definition(
                session, key="reviewer", display_name="Custom",
            )
            await session.commit()

            defn = await agent_definition_service.reset_definition(session, "reviewer")
            await session.commit()

            expected = get_default_agent_definition("reviewer")
            assert defn.display_name == expected.display_name
            assert defn.source == "builtin"

            db_record = await agent_definition_repo.get_by_key(session, "reviewer")
            assert db_record is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reset_custom_raises_validation_error():
    from app.storage.services import agent_definition_service

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            await agent_definition_service.create_definition(
                session,
                key="custom-only",
                display_name="Custom Only",
                description="",
                kind="subagent",
                prompt_agent_name="custom-only",
                model_id=None,
                enabled_tool_categories=[],
                enabled_skills=[],
                metadata={},
                delegatable_agents=[],
            )
            await session.commit()

            with pytest.raises(ValidationError, match="只有内置智能体可以重置"):
                await agent_definition_service.reset_definition(session, "custom-only")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_custom_definition():
    from app.storage.services import agent_definition_service
    from app.storage.repos import agent_definition_repo

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            await agent_definition_service.create_definition(
                session,
                key="del-me",
                display_name="Delete Me",
                description="",
                kind="subagent",
                prompt_agent_name="del-me",
                model_id=None,
                enabled_tool_categories=[],
                enabled_skills=[],
                metadata={},
                delegatable_agents=[],
            )
            await session.commit()

            await agent_definition_service.delete_definition(session, "del-me")
            await session.commit()

            record = await agent_definition_repo.get_by_key(session, "del-me")
            assert record is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_nonexistent_raises_not_found():
    from app.storage.services import agent_definition_service

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            with pytest.raises(NotFoundError):
                await agent_definition_service.delete_definition(session, "nonexistent")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_removes_delegatable_reference_from_primaries():
    from app.storage.services import agent_definition_service
    from app.storage.repos import agent_definition_repo
    from app.agent_runtime.persistence.model import AgentDefinitionRecord

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        async with factory() as session:
            session.add(
                AgentDefinitionRecord(
                    key="primary",
                    display_name="Primary",
                    description="",
                    kind="primary",
                    prompt_agent_name="primary",
                    enabled_tool_categories=[],
                    enabled_skills=[],
                    source="builtin",
                    delegatable_agents=["explorer", "target-bot"],
                )
            )
            await agent_definition_service.create_definition(
                session,
                key="target-bot",
                display_name="Target Bot",
                description="",
                kind="subagent",
                prompt_agent_name="target-bot",
                model_id=None,
                enabled_tool_categories=[],
                enabled_skills=[],
                metadata={},
                delegatable_agents=[],
            )
            await session.commit()

            await agent_definition_service.delete_definition(session, "target-bot")
            await session.commit()

            primary = await agent_definition_repo.get_by_key(session, "primary")
            assert primary is not None
            assert "target-bot" not in primary.delegatable_agents
            assert "explorer" in primary.delegatable_agents
    finally:
        await engine.dispose()
