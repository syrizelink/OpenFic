# -*- coding: utf-8 -*-
"""
Google Drive v3 REST 客户端（httpx 直连）。

负责创建/查找 OpenFic 文件夹、把 HTML 导入为 Google Doc，以及更新/删除文档。
"""

from __future__ import annotations

import json

import httpx

from app.google_drive import config as drive_config
from app.google_drive.errors import DriveApiError, DriveAuthError


class DriveClient:
    """基于已有 access token 的 Drive API 客户端。"""

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    async def ensure_folder(self, folder_id: str | None) -> str:
        """返回 OpenFic 文件夹 ID；不存在时在根目录创建。"""
        if folder_id:
            try:
                metadata = await self.get_file(folder_id)
                if metadata.get("mimeType") == "application/vnd.google-apps.folder":
                    return folder_id
            except DriveApiError:
                pass

        name = drive_config.DRIVE_FOLDER_NAME
        existing = await self._find_folder(name)
        if existing:
            return existing

        created = await self._request(
            "POST", "/drive/v3/files",
            params={"fields": "id,name,mimeType"},
            json={"name": name, "mimeType": "application/vnd.google-apps.folder"},
        )
        folder_id = created.get("id")
        if not isinstance(folder_id, str):
            raise DriveApiError("创建 OpenFic 文件夹失败：响应缺少 id")
        return folder_id

    async def find_document(self, folder_id: str, name: str) -> str | None:
        """在文件夹中按名字查找 Google Doc，返回文件 ID。"""
        q = (
            f"'{folder_id}' in parents and name='{_escape_query(name)}' "
            "and trashed=false"
        )
        result = await self._request(
            "GET", "/drive/v3/files",
            params={"q": q, "fields": "files(id,name)", "spaces": "drive"},
        )
        files = result.get("files")
        if not isinstance(files, list) or not files:
            return None
        file_id = files[0].get("id")
        return file_id if isinstance(file_id, str) else None

    async def create_document(self, folder_id: str, name: str, html: str) -> dict[str, object]:
        """把 HTML 导入为 Google Doc，返回文件元数据。"""
        metadata = {
            "name": name,
            "mimeType": drive_config.GOOGLE_DOCS_MIME,
            "parents": [folder_id],
        }
        return await self._upload(
            "POST", "/upload/drive/v3/files",
            params={"uploadType": "multipart", "fields": "id,name,mimeType,webViewLink"},
            metadata=metadata,
            html=html,
        )

    async def update_document(self, file_id: str, html: str) -> dict[str, object]:
        """用新 HTML 整份替换 Google Doc 内容（保留同一文件 ID）。"""
        return await self._upload(
            "PATCH", f"/upload/drive/v3/files/{file_id}",
            params={"uploadType": "multipart", "fields": "id,name,mimeType,webViewLink"},
            metadata={},
            html=html,
        )

    async def get_file(self, file_id: str) -> dict[str, object]:
        return await self._request(
            "GET", f"/drive/v3/files/{file_id}",
            params={"fields": "id,name,mimeType,webViewLink"},
        )

    async def delete_file(self, file_id: str) -> None:
        await self._request("DELETE", f"/drive/v3/files/{file_id}")

    async def _find_folder(self, name: str) -> str | None:
        q = (
            f"name='{_escape_query(name)}' and "
            "mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        result = await self._request(
            "GET", "/drive/v3/files",
            params={"q": q, "fields": "files(id,name)", "spaces": "drive"},
        )
        files = result.get("files")
        if not isinstance(files, list) or not files:
            return None
        folder_id = files[0].get("id")
        return folder_id if isinstance(folder_id, str) else None

    async def _upload(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str],
        metadata: dict[str, object],
        html: str,
    ) -> dict[str, object]:
        boundary = "openfic-boundary-" + "123456789012345678901234"
        body = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
            + json.dumps(metadata, ensure_ascii=False)
            + "\r\n"
            f"--{boundary}\r\n"
            "Content-Type: text/html; charset=UTF-8\r\n\r\n"
            + html
            + "\r\n"
            f"--{boundary}--\r\n"
        )
        headers = {
            **self._headers,
            "Content-Type": f"multipart/related; boundary={boundary}",
        }
        async with httpx.AsyncClient(timeout=120) as http:
            response = await http.request(
                method,
                f"{drive_config.DRIVE_API_BASE}{url}",
                params=params,
                headers=headers,
                content=body.encode("utf-8"),
            )
        return await self._handle_response(response, url)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
    ) -> dict[str, object]:
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.request(
                method,
                f"{drive_config.DRIVE_API_BASE}{url}",
                params=params,
                headers=self._headers,
                json=json,
            )
        return await self._handle_response(response, url)

    async def _handle_response(
        self, response: httpx.Response, url: str
    ) -> dict[str, object]:
        if response.status_code in {200, 201}:
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        if response.status_code == 204:
            return {}
        if response.status_code in {401, 403}:
            raise DriveAuthError(f"Google 授权失效（{response.status_code}）")
        if response.status_code == 404:
            raise DriveApiError(f"文件不存在: {url}")
        raise DriveApiError(f"Drive API 错误 {response.status_code}: {response.text[:300]}")


def _escape_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")
