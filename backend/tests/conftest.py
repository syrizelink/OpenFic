# -*- coding: utf-8 -*-
"""
测试配置。

使用 module-scoped 引擎避免每个测试重建引擎和全部表，
通过每测试连接级事务回滚实现隔离。
"""

from collections.abc import AsyncGenerator
from pathlib import Path
import shutil

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.api.exceptions import register_exception_handlers
from app.api.routers import (
    agent_rules,
    agent_definitions,
    agent_runtime,
    background,
    characters,
    chapter_context,
    chapters,
    dashboard,
    health,
    import_router,
    model_icons,
    model_provider_catalog,
    model_providers,
    models,
    notes,
    projects,
    prompt_chains,
    retrieval_index,
    skills,
    settings,
    tasks,
    volumes,
    world_info,
    world_info_entries,
)
from app.models.catalog import CatalogIconProxyService
from app.storage.database import get_session
from tests.model_registry import register_sqlmodel_models


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_per_test_session: AsyncSession | None = None


def _create_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.state.catalog_icon_proxy_service = CatalogIconProxyService()
    test_app.include_router(model_icons.router)
    test_app.include_router(health.router, prefix="/api/v1")
    test_app.include_router(projects.router, prefix="/api/v1")
    test_app.include_router(volumes.router, prefix="/api/v1")
    test_app.include_router(chapters.router, prefix="/api/v1")
    test_app.include_router(notes.router, prefix="/api/v1")
    test_app.include_router(characters.router, prefix="/api/v1")
    test_app.include_router(world_info.router, prefix="/api/v1")
    test_app.include_router(world_info_entries.router, prefix="/api/v1")
    test_app.include_router(settings.router, prefix="/api/v1")
    test_app.include_router(import_router.router, prefix="/api/v1")
    test_app.include_router(model_providers.router, prefix="/api/v1")
    test_app.include_router(model_provider_catalog.router, prefix="/api/v1")
    test_app.include_router(models.router, prefix="/api/v1")
    test_app.include_router(prompt_chains.router, prefix="/api/v1")
    test_app.include_router(agent_definitions.router, prefix="/api/v1")
    test_app.include_router(agent_rules.router, prefix="/api/v1")
    test_app.include_router(retrieval_index.router, prefix="/api/v1")
    test_app.include_router(retrieval_index.global_router, prefix="/api/v1")
    test_app.include_router(skills.router, prefix="/api/v1")
    test_app.include_router(chapter_context.router, prefix="/api/v1")
    test_app.include_router(tasks.router, prefix="/api/v1")
    test_app.include_router(agent_runtime.router, prefix="/api/v1/agent")
    test_app.include_router(background.router, prefix="/api/v1")
    test_app.include_router(dashboard.router, prefix="/api/v1")
    register_exception_handlers(test_app)
    return test_app


async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
    if _per_test_session is None:
        raise RuntimeError("No active test session")
    yield _per_test_session


@pytest_asyncio.fixture(scope="module")
async def db_engine():
    """Module-scoped 引擎：同一模块的测试共享引擎和表结构。"""
    register_sqlmodel_models()
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def _test_app():
    """Module-scoped FastAPI 测试应用。"""
    test_app = _create_test_app()
    test_app.dependency_overrides[get_session] = _override_get_session
    return test_app


@pytest_asyncio.fixture
async def client(_test_app: FastAPI, db_engine) -> AsyncGenerator[AsyncClient, None]:
    """每个测试的 HTTP 客户端。通过连接级事务实现隔离。"""
    global _per_test_session
    async with db_engine.begin() as setup_conn:
        await setup_conn.run_sync(SQLModel.metadata.create_all)

    async with db_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            autoflush=False,
        )
        _per_test_session = session

        async with AsyncClient(
            transport=ASGITransport(app=_test_app),
            base_url="http://test",
        ) as http_client:
            yield http_client

        await conn.rollback()
        await session.close()
        _per_test_session = None


@pytest_asyncio.fixture(autouse=True)
async def _reset_icon_proxy(_test_app: FastAPI):
    """每次测试前重置图标代理，避免 session-shared 状态泄漏。"""
    _test_app.state.catalog_icon_proxy_service = CatalogIconProxyService()
    yield
    await _test_app.state.catalog_icon_proxy_service.aclose()


@pytest_asyncio.fixture(autouse=True)
async def isolated_prompts_dir(monkeypatch, tmp_path: Path) -> AsyncGenerator[Path, None]:
    """每个测试使用隔离的 prompts 目录，避免污染仓库内 YAML。"""
    import app.prompts.loader as prompt_loader

    source_dir = prompt_loader.PROMPTS_DIR
    prompts_dir = tmp_path / "prompts"
    shutil.copytree(source_dir, prompts_dir)
    monkeypatch.setattr(prompt_loader, "PROMPTS_DIR", prompts_dir)

    try:
        yield prompts_dir
    finally:
        shutil.rmtree(prompts_dir, ignore_errors=True)


@pytest_asyncio.fixture
async def session(client: AsyncClient) -> AsyncGenerator[AsyncSession, None]:
    """向后兼容：从 app 覆盖中获取与 client 相同的数据库会话。"""
    app = client._transport.app  # type: ignore
    session_generator = app.dependency_overrides[get_session]
    async for sess in session_generator():
        yield sess
