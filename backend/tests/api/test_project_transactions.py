import os
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.types import Message, Receive, Scope, Send

from app.api.routers import projects
from app.storage import database
from app.storage.models.project import Project
from app.storage.models.volume import Volume


@pytest.fixture(params=["sqlite", "postgresql"])
async def transaction_sessions(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    schema = None
    if request.param == "postgresql":
        database_url = os.getenv("OPENFIC_TEST_DATABASE_URL", "")
        if not database_url.startswith("postgresql"):
            pytest.skip("Set OPENFIC_TEST_DATABASE_URL to test PostgreSQL transactions")
        schema = "response_transactions_" + uuid4().hex
        setup_engine = create_async_engine(database_url)
        try:
            async with setup_engine.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        finally:
            await setup_engine.dispose()
        database_url = make_url(database_url).update_query_dict({"options": f"-csearch_path={schema}"})
    else:
        database_url = f"sqlite+aiosqlite:///{tmp_path / 'transactions.db'}"
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Project.metadata.create_all, tables=[Project.__table__, Volume.__table__])
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        monkeypatch.setattr(database, "_get_session_factory", lambda: factory)
        yield factory
    finally:
        if schema:
            async with engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await engine.dispose()


async def test_project_is_committed_before_success_response_starts(
    transaction_sessions: async_sessionmaker[AsyncSession],
) -> None:
    app = FastAPI()
    app.include_router(projects.router, prefix="/api/v1")
    visible_counts = []

    async def probe(scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_commit_check(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] == 201:
                async with transaction_sessions() as reader:
                    visible_counts.append(await reader.scalar(select(func.count()).select_from(Project)))
            await send(message)

        await app(scope, receive, send_with_commit_check)

    async with AsyncClient(transport=ASGITransport(app=probe), base_url="http://test") as client:
        response = await client.post("/api/v1/projects", data={"title": "Committed before response"})
        assert response.status_code == 201
        assert visible_counts == [1]
        listed = await client.get("/api/v1/projects")
        assert listed.json()["total"] == 1


async def test_commit_failure_returns_error_instead_of_success(
    transaction_sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    app.include_router(projects.router, prefix="/api/v1")

    async def fail_commit(session: AsyncSession) -> None:
        raise RuntimeError("Transaction commit failed")

    monkeypatch.setattr(AsyncSession, "commit", fail_commit)
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
    ) as client:
        response = await client.post("/api/v1/projects", data={"title": "Must not report success"})
    assert response.status_code == 500
    async with transaction_sessions() as reader:
        assert await reader.scalar(select(func.count()).select_from(Project)) == 0
