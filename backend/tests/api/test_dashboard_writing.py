# -*- coding: utf-8 -*-
"""
Uji API aktivitas penulisan Dashboard.
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.writing_activity_event import WritingActivityEvent


def _track_sql_statements(session: AsyncSession) -> tuple[list[str], object]:
    statements: list[str] = []
    bind = session.sync_session.get_bind()

    def before_cursor_execute(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(bind, "before_cursor_execute", before_cursor_execute)
    return statements, before_cursor_execute


def _stop_tracking_sql(session: AsyncSession, listener: object) -> None:
    event.remove(session.sync_session.get_bind(), "before_cursor_execute", listener)


async def _create_project(client: AsyncClient) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/projects",
        data={"title": "Novel Uji"},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]
    volumes_response = await client.get(f"/api/v1/projects/{project_id}/volumes")
    assert volumes_response.status_code == 200
    volumes = volumes_response.json()
    assert len(volumes) == 1
    return project_id, volumes[0]["id"]


@pytest.mark.asyncio
async def test_writing_dashboard_tracks_user_chapter_edits(client: AsyncClient) -> None:
    """Uji dasbor penulisan menghitung peristiwa pembuatan, pembaruan, dan penghapusan bab oleh pengguna."""
    project_id, volume_id = await _create_project(client)

    create_response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": volume_id, "title": "Bab 1", "content": "Satu dua tiga"},
    )
    assert create_response.status_code == 201
    chapter_id = create_response.json()["id"]
    assert create_response.json()["word_count"] == 3

    update_response = await client.patch(
        f"/api/v1/chapters/{chapter_id}",
        json={"content": "Satu dua tiga empat lima"},
    )
    assert update_response.json()["word_count"] == 5

    delete_response = await client.delete(f"/api/v1/chapters/{chapter_id}")
    assert delete_response.status_code == 204

    response = await client.get(
        "/api/v1/dashboard/writing",
        params={"project_id": project_id, "source": "user"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["summary"]["active_days"] == 1
    assert len(data["time_series"]) == 1
    assert data["time_series"][0]["user_word_delta"] == 0


@pytest.mark.asyncio
async def test_writing_dashboard_separates_sources(client: AsyncClient) -> None:
    """Uji dasbor penulisan dapat difilter per sumber agar data pengguna dan data impor tidak tertukar."""
    project_id, volume_id = await _create_project(client)

    create_response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": volume_id, "title": "Bab 1", "content": "Isi utama pengguna"},
    )
    assert create_response.status_code == 201

    all_response = await client.get(
        "/api/v1/dashboard/writing",
        params={"project_id": project_id},
    )
    user_response = await client.get(
        "/api/v1/dashboard/writing",
        params={"project_id": project_id, "source": "user"},
    )
    agent_response = await client.get(
        "/api/v1/dashboard/writing",
        params={"project_id": project_id, "source": "agent"},
    )

    assert all_response.status_code == 200
    assert user_response.status_code == 200
    assert agent_response.status_code == 200
    assert all_response.json()["summary"]["active_days"] == 1
    assert user_response.json()["summary"]["active_days"] == 1
    assert agent_response.json()["summary"]["active_days"] == 0


@pytest.mark.asyncio
async def test_writing_dashboard_groups_activity_by_user_timezone(client: AsyncClient, session: AsyncSession) -> None:
    """Uji aktivitas penulisan mengikuti tanggal zona waktu pengguna, bukan langsung memakai tanggal UTC."""
    project_id, volume_id = await _create_project(client)

    create_response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": volume_id, "title": "Bab 1", "content": "Menulis dini hari"},
    )
    assert create_response.status_code == 201
    await session.execute(
        update(WritingActivityEvent)
        .where(col(WritingActivityEvent.project_id) == project_id)
        .values(created_at=datetime(2026, 5, 8, 16, 30, tzinfo=UTC))
    )
    await session.commit()

    response = await client.get(
        "/api/v1/dashboard/writing",
        params={
            "project_id": project_id,
            "start_at": "2026-05-09T00:00:00",
            "end_at": "2026-05-09T23:59:59",
            "timezone": "Asia/Shanghai",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["active_days"] == 1
    assert data["time_series"][0]["date"] == "2026-05-09"


@pytest.mark.asyncio
async def test_writing_dashboard_reads_activity_events_once(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    session.add(
        WritingActivityEvent(
            project_id="project-id",
            source="user",
            operation="update",
            chapter_id="chapter-id",
            word_delta=3,
        )
    )
    await session.commit()
    statements, listener = _track_sql_statements(session)

    try:
        response = await client.get("/api/v1/dashboard/writing")
    finally:
        _stop_tracking_sql(session, listener)

    assert response.status_code == 200
    assert len(statements) == 1
    assert "GROUP BY" in statements[0].upper()
