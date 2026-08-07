# -*- coding: utf-8 -*-
"""Google Drive 同步 API 测试。"""

import pytest
from httpx import AsyncClient

from app.google_drive import config as drive_config
from app.storage.repos import chapter_repo, project_repo, volume_repo
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.volume import Volume


async def _create_project(client: AsyncClient) -> tuple[str, str]:
    response = await client.post("/api/v1/projects", data={"title": "同步测试小说"})
    assert response.status_code == 201
    project_id = response.json()["id"]
    volumes = (await client.get(f"/api/v1/projects/{project_id}/volumes")).json()
    return project_id, volumes[0]["id"]


@pytest.mark.asyncio
async def test_get_config_default(client: AsyncClient) -> None:
    response = await client.get("/api/v1/drive/config")
    assert response.status_code == 200
    data = response.json()
    assert data["has_credentials"] is False
    assert data["connected"] is False
    assert data["interval_minutes"] == 10
    assert data["redirect_uri"].startswith("http://127.0.0.1")


@pytest.mark.asyncio
async def test_update_config_requires_both_credentials(client: AsyncClient) -> None:
    response = await client.put("/api/v1/drive/config", json={"client_id": "abc"})
    assert response.status_code == 400
    assert "同时提供" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_config_sets_credentials_and_interval(client: AsyncClient) -> None:
    response = await client.put(
        "/api/v1/drive/config",
        json={"client_id": "client-id", "client_secret": "client-secret", "interval_minutes": 30},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_credentials"] is True
    assert data["interval_minutes"] == 30


@pytest.mark.asyncio
async def test_update_config_encrypts_credentials(client: AsyncClient, session) -> None:
    await client.put(
        "/api/v1/drive/config",
        json={"client_id": "secret-client-id", "client_secret": "secret"},
    )
    raw = await drive_config.get_value(
        session, "drive_google_client_id"
    )
    assert raw is not None
    assert "secret-client-id" not in raw  # 密文存储


@pytest.mark.asyncio
async def test_auth_url_requires_credentials(client: AsyncClient) -> None:
    response = await client.get("/api/v1/drive/auth-url")
    assert response.status_code == 400
    assert "配置" in response.json()["detail"]


@pytest.mark.asyncio
async def test_auth_url_builds_google_url(client: AsyncClient) -> None:
    await client.put(
        "/api/v1/drive/config",
        json={"client_id": "cid", "client_secret": "csecret"},
    )
    response = await client.get("/api/v1/drive/auth-url")
    assert response.status_code == 200
    auth_url = response.json()["auth_url"]
    assert "accounts.google.com/o/oauth2/v2/auth" in auth_url
    assert "client_id=cid" in auth_url
    assert "access_type=offline" in auth_url
    assert "prompt=consent" in auth_url


@pytest.mark.asyncio
async def test_callback_rejects_bad_state(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/drive/oauth/callback", params={"code": "abc", "state": "nope"}
    )
    assert response.status_code == 200
    assert "失败" in response.text


@pytest.mark.asyncio
async def test_project_status_and_toggle(client: AsyncClient, session) -> None:
    project_id, volume_id = await _create_project(client)
    volume = await volume_repo.get_by_id(session, volume_id)
    assert volume is not None
    await chapter_repo.create(
        session,
        Chapter(
            project_id=project_id,
            volume_id=volume_id,
            title="第一章",
            content="内容",
            order=1,
        ),
    )
    await session.commit()

    status = await client.get(f"/api/v1/drive/projects/{project_id}")
    assert status.status_code == 200
    assert status.json()["enabled"] is False
    assert status.json()["chapter_count"] == 1

    toggled = await client.put(
        f"/api/v1/drive/projects/{project_id}", json={"enabled": True}
    )
    assert toggled.status_code == 200
    assert toggled.json()["enabled"] is True
    assert await drive_config.is_project_dirty(session, project_id)

    disabled = await client.put(
        f"/api/v1/drive/projects/{project_id}", json={"enabled": False}
    )
    assert disabled.json()["enabled"] is False


@pytest.mark.asyncio
async def test_project_status_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/drive/projects/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_manual_sync_error_when_not_connected(client: AsyncClient) -> None:
    project_id, _ = await _create_project(client)
    response = await client.post(f"/api/v1/drive/projects/{project_id}/sync")
    assert response.status_code == 502
    assert "尚未连接" in response.json()["detail"]


@pytest.mark.asyncio
async def test_manual_sync_success(
    client: AsyncClient, monkeypatch, session
) -> None:
    project_id, volume_id = await _create_project(client)
    response = await client.post(
        f"/api/v1/projects/{project_id}/chapters",
        json={"volume_id": volume_id, "title": "第一章", "content": "内容"},
    )
    assert response.status_code == 201

    await drive_config.set_refresh_token(session, "fake-refresh")
    await session.commit()

    class _FakeClient:
        def __init__(self, token: str) -> None:
            pass

        async def ensure_folder(self, folder_id):
            return "folder-1"

        async def find_document(self, folder_id, name):
            return None

        async def create_document(self, folder_id, name, html):
            return {
                "id": "file-1",
                "name": name,
                "mimeType": "application/vnd.google-apps.document",
                "webViewLink": "https://docs.google.com/document/d/file-1/edit",
            }

        async def update_document(self, file_id, html):
            return {"id": file_id}

    monkeypatch.setattr("app.google_drive.service.DriveClient", _FakeClient)
    monkeypatch.setattr(
        "app.google_drive.service.oauth.get_access_token",
        lambda session: _fake_token(),
    )

    response = await client.post(f"/api/v1/drive/projects/{project_id}/sync")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "synced"
    assert data["file_id"] == "file-1"


async def _fake_token() -> str:
    return "fake-token"
