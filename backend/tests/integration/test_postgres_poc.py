from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from zoneinfo import ZoneInfo

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint
from sqlalchemy import delete

import app.settings as app_settings
from app.agent_runtime.runner.checkpointer import (
    checkpoint_free_page_bytes,
    delete_checkpoints_after_for_thread,
    delete_checkpoints_for_thread,
    get_checkpointer,
    latest_checkpoint_id_for_thread,
    prune_checkpoints_for_thread,
    reset_checkpointer,
)
from app.storage.database import close_db, create_session
from app.storage.models.llm_audit_log import LLMAuditLog
from app.storage.models.project import Project
from app.storage.models.revision_content_blob import RevisionContentBlob
from app.storage.models.writing_activity_event import WritingActivityEvent
from app.storage.repos import (
    dashboard_repo,
    project_repo,
    revision_content_blob_repo,
    writing_activity_repo,
)


POSTGRES_URL: str | None = None
CHECKPOINT_URL: str | None = None


@pytest.fixture(autouse=True)
def isolated_databases(postgres_database_factory, monkeypatch):
    from app.storage.sqlite_to_postgres import prepare_postgres_schema

    business = postgres_database_factory()
    checkpoint = postgres_database_factory()
    prepare_postgres_schema(business)
    monkeypatch.setattr(__import__(__name__, fromlist=["*"]), "POSTGRES_URL", business)
    monkeypatch.setattr(__import__(__name__, fromlist=["*"]), "CHECKPOINT_URL", checkpoint)


@pytest.mark.asyncio
async def test_postgres_business_database_and_checkpointer() -> None:
    assert POSTGRES_URL is not None
    assert CHECKPOINT_URL is not None
    original_database_url = app_settings.settings.database_url_override
    original_checkpoint_url = app_settings.settings.checkpoint_database_url
    project_id = "postgres-poc-project"
    checkpoint_thread_id = "postgres-poc-checkpoint"
    try:
        app_settings.settings.database_url_override = POSTGRES_URL
        app_settings.settings.checkpoint_database_url = CHECKPOINT_URL
        await close_db()
        await reset_checkpointer()

        session = await create_session()
        blob_id: str | None = None
        try:
            await session.execute(delete(Project).where(Project.id == project_id))
            project = Project(
                id=project_id,
                title="测试项目",
                description="用于 PostgreSQL 拼音检索验证",
            )
            await project_repo.create(session, project)
            blob_id = await revision_content_blob_repo.put(session, "内容" * 600)
            await session.commit()

            matches = await project_repo.list_all(session, search="ceshixiangmu")
            assert [item.id for item in matches] == [project_id]
            assert blob_id is not None
            assert await revision_content_blob_repo.get(session, blob_id) == "内容" * 600
            assert await revision_content_blob_repo.put(session, "内容" * 600) == blob_id
            project.title = "新项目"
            await project_repo.update(session, project)
            assert await project_repo.list_all(session, search="ceshixiangmu") == []
            assert [item.id for item in await project_repo.list_all(session, search="xxm")] == [project_id]
        finally:
            await session.rollback()
            await session.execute(delete(Project).where(Project.id == project_id))
            if blob_id is not None:
                await session.execute(
                    delete(RevisionContentBlob).where(RevisionContentBlob.id == blob_id)
                )
            await session.commit()
            await session.close()

        await delete_checkpoints_for_thread(checkpoint_thread_id)
        checkpointer = await get_checkpointer()
        config = cast(
            RunnableConfig,
            {
                "configurable": {
                    "thread_id": checkpoint_thread_id,
                    "checkpoint_ns": "",
                }
            },
        )
        checkpoint = cast(
            Checkpoint,
            {
                "v": 2,
                "id": "00000000-0000-6000-8000-000000000001",
                "ts": datetime.now(UTC).isoformat(),
                "channel_values": {"value": "persisted"},
                "channel_versions": {"value": "1"},
                "versions_seen": {},
                "pending_sends": [],
            },
        )
        saved_config = await checkpointer.aput(
            config,
            checkpoint,
            {},
            checkpoint["channel_versions"],
        )
        await checkpointer.aput_writes(
            saved_config,
            [("result", "complete")],
            "postgres-poc-task",
        )
        restored = await checkpointer.aget_tuple(saved_config)
        assert restored is not None
        assert restored.checkpoint["channel_values"]["value"] == "persisted"
        assert restored.pending_writes == [
            ("postgres-poc-task", "result", "complete")
        ]
        second_checkpoint = cast(
            Checkpoint,
            {
                **checkpoint,
                "id": "00000000-0000-6000-8000-000000000002",
                "channel_values": {"value": "latest"},
                "channel_versions": {"value": "2"},
            },
        )
        latest_config = await checkpointer.aput(
            saved_config,
            second_checkpoint,
            {},
            second_checkpoint["channel_versions"],
        )
        third_checkpoint = cast(Checkpoint, {
            **second_checkpoint,
            "id": "00000000-0000-6000-8000-000000000003",
            "channel_values": {"value": "discard"},
            "channel_versions": {"value": "3"},
        })
        third_config = await checkpointer.aput(
            latest_config, third_checkpoint, {}, third_checkpoint["channel_versions"],
        )
        assert await delete_checkpoints_after_for_thread(checkpoint_thread_id, second_checkpoint["id"]) > 0
        assert await checkpointer.aget_tuple(third_config) is None
        # Both retained checkpoints remain readable after unreferenced-blob cleanup.
        assert await checkpointer.aget_tuple(saved_config) is not None
        assert await checkpointer.aget_tuple(latest_config) is not None
        assert (
            await prune_checkpoints_for_thread(
                checkpointer,
                checkpoint_thread_id,
                set(),
            )
            > 0
        )
        assert await checkpointer.aget_tuple(saved_config) is None
        latest = await checkpointer.aget_tuple(latest_config)
        assert latest is not None
        assert latest.checkpoint["channel_values"]["value"] == "latest"
        assert await latest_checkpoint_id_for_thread(checkpoint_thread_id) == (
            second_checkpoint["id"]
        )
        assert await checkpoint_free_page_bytes() == (0, 0)
        assert await delete_checkpoints_for_thread(checkpoint_thread_id) > 0
        async with checkpointer.conn.cursor() as cursor:
            for table in ("checkpoints", "checkpoint_writes", "checkpoint_blobs"):
                await cursor.execute(f"SELECT count(*) AS n FROM {table} WHERE thread_id = %s", (checkpoint_thread_id,))
                assert (await cursor.fetchone())["n"] == 0
    finally:
        await reset_checkpointer()
        await close_db()
        app_settings.settings.database_url_override = original_database_url
        app_settings.settings.checkpoint_database_url = original_checkpoint_url


@pytest.mark.asyncio
@pytest.mark.parametrize("zone, expected_date", [("UTC", "2026-05-08"), ("Asia/Shanghai", "2026-05-09"), ("America/New_York", "2026-05-08")])
async def test_postgres_dashboard_aggregates(zone, expected_date) -> None:
    assert POSTGRES_URL is not None
    original_database_url = app_settings.settings.database_url_override
    project_id = "postgres-dashboard-project"
    audit_id = "postgres-dashboard-audit"
    activity_id = "postgres-dashboard-activity"
    try:
        app_settings.settings.database_url_override = POSTGRES_URL
        await close_db()
        session = await create_session()
        try:
            await session.execute(delete(LLMAuditLog).where(LLMAuditLog.id == audit_id))
            await session.execute(
                delete(WritingActivityEvent).where(WritingActivityEvent.id == activity_id)
            )
            await session.execute(delete(Project).where(Project.id == project_id))
            await project_repo.create(
                session,
                Project(id=project_id, title="统计项目", description="PostgreSQL"),
            )
            session.add(
                LLMAuditLog(
                    id=audit_id,
                    project_id=project_id,
                    operation="generate",
                    model_id="postgres-model",
                    model_provider="test",
                    status="success",
                    tokens_input=2,
                    tokens_output=3,
                    tokens_total=5,
                    created_at=datetime(2026, 5, 8, 16, 30, tzinfo=UTC),
                )
            )
            session.add(
                WritingActivityEvent(
                    id=activity_id,
                    project_id=project_id,
                    source="user",
                    operation="update",
                    chapter_id="postgres-chapter",
                    word_delta=9,
                    created_at=datetime(2026, 5, 8, 16, 30, tzinfo=UTC),
                )
            )
            await session.commit()

            dashboard = await dashboard_repo.get_stats(
                session,
                dashboard_repo.DashboardFilters(project_id=project_id),
            )
            assert dashboard.summary.calls_total == 1
            assert dashboard.summary.tokens_total == 5
            assert dashboard.model_time_series[0].date == "2026-05-08"

            writing = await writing_activity_repo.get_aggregates(
                session,
                writing_activity_repo.WritingActivityFilters(
                    project_id=project_id,
                    timezone=ZoneInfo(zone),
                ),
            )
            assert writing is not None
            assert writing.summary.active_days == 1
            assert writing.time_series[0].date == expected_date
            assert writing.time_series[0].user_word_delta == 9
        finally:
            await session.rollback()
            await session.execute(delete(LLMAuditLog).where(LLMAuditLog.id == audit_id))
            await session.execute(
                delete(WritingActivityEvent).where(WritingActivityEvent.id == activity_id)
            )
            await session.execute(delete(Project).where(Project.id == project_id))
            await session.commit()
            await session.close()
    finally:
        await close_db()
        app_settings.settings.database_url_override = original_database_url
