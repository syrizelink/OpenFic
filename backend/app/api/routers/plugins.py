"""Authenticated extension management and versioned plugin RPC transport."""

import io
import json
import mimetypes
import zipfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, Response, HTMLResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.plugins.host import PluginError, PluginHost
from app.plugins.manifest import (
    API_VERSION,
    MAX_PACKAGE_BYTES,
    SDK_VERSION,
    UI_SLOTS,
    CAPABILITIES,
)
from app.storage.database import get_session

router = APIRouter(prefix="/plugins", tags=["plugins"])
asset_router = APIRouter(prefix="/plugin-assets", tags=["plugin views"])
oauth_router = APIRouter(prefix="/plugin-oauth", tags=["plugin OAuth"])


ASSET_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'",
}


def host(request: Request) -> PluginHost:
    return request.app.state.plugin_host


Host = Annotated[PluginHost, Depends(host)]


@oauth_router.get("/callback", response_class=HTMLResponse)
async def oauth_callback(
    manager: Host, state: str = "", code: str | None = None, error: str | None = None
):
    from app.plugins.oauth import finish_oauth

    try:
        await finish_oauth(manager, state, code, error)
    except ValueError as exc:
        raise PluginError(str(exc), 400) from exc
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><title>OpenFic</title><p>授权成功。请关闭此页面，返回 OpenFic 插件。</p>",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


class EnableRequest(BaseModel):
    enabled: bool


class ConfigurationRequest(BaseModel):
    settings: dict[str, Any]


class CallRequest(BaseModel):
    method: str = Field(min_length=1, max_length=80)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def bounded_params(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > 64_000:
            raise ValueError("RPC parameters exceed 64 KB")
        return value


async def read_package(file: UploadFile, trusted: bool) -> bytes:
    if not trusted:
        raise PluginError("Installation requires acknowledging trusted-code execution")
    content = await file.read(MAX_PACKAGE_BYTES + 1)
    if len(content) > MAX_PACKAGE_BYTES:
        raise PluginError("Package exceeds 20 MiB")
    return content


@router.get("")
async def list_plugins(manager: Host):
    return {
        "api_version": API_VERSION,
        "sdk_version": SDK_VERSION,
        "slots": UI_SLOTS,
        "plugins": [manager.describe(p) for p in manager.plugins.values()],
    }


@router.get("/catalogue")
async def sdk_catalogue():
    from app.plugins.gateway import BusinessAPI
    from app.plugins.runtime import EVENTS

    return {
        "version": SDK_VERSION,
        "capabilities": sorted(CAPABILITIES),
        "slots": UI_SLOTS,
        "events": sorted(EVENTS),
        **BusinessAPI.catalogue(),
    }


@router.post("", status_code=201)
async def install_plugin(
    manager: Host,
    file: Annotated[UploadFile, File()],
    trusted: Annotated[bool, Form()] = False,
):
    return await manager.install(await read_package(file, trusted))


@router.get("/sdk.js")
async def frontend_sdk():
    return FileResponse(
        Path(__file__).parents[2] / "plugins" / "frontend-sdk.js",
        media_type="text/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.put("/{plugin_id}/package")
async def update_plugin(
    plugin_id: str,
    manager: Host,
    file: Annotated[UploadFile, File()],
    trusted: Annotated[bool, Form()] = False,
):
    return await manager.install(await read_package(file, trusted), update_id=plugin_id)


@router.get("/{plugin_id}/package")
async def export_plugin(plugin_id: str, manager: Host):
    plugin = manager.get(plugin_id)
    buffer = io.BytesIO()
    directory = manager.root / plugin_id
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if (
                path.is_file()
                and not path.is_symlink()
                and "__pycache__" not in path.parts
            ):
                archive.write(path, path.relative_to(directory).as_posix())
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{plugin_id}-{plugin.manifest.version}.zip"'
        },
    )


@router.patch("/{plugin_id}/enabled")
async def enable_plugin(plugin_id: str, data: EnableRequest, manager: Host):
    return await manager.set_enabled(plugin_id, data.enabled)


@router.put("/{plugin_id}/settings")
async def configure_plugin(plugin_id: str, data: ConfigurationRequest, manager: Host):
    return await manager.configure(plugin_id, data.settings)


@router.get("/{plugin_id}/logs")
async def plugin_logs(plugin_id: str, manager: Host):
    return manager.logs(plugin_id)


@router.delete("/{plugin_id}", status_code=204)
async def uninstall_plugin(plugin_id: str, manager: Host):
    await manager.uninstall(plugin_id)


@router.post("/{plugin_id}/rpc")
async def call_plugin(
    plugin_id: str,
    data: CallRequest,
    manager: Host,
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    return {
        "result": await manager.call(
            plugin_id,
            data.method,
            data.params,
            session,
            runtime={"backend_url": str(request.base_url).rstrip("/")},
        )
    }


@router.get("/{plugin_id}/assets/{filename:path}")
async def plugin_asset(plugin_id: str, filename: str, manager: Host):
    path = manager.asset(plugin_id, filename)
    return FileResponse(
        path,
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        headers=ASSET_HEADERS,
    )


@router.post("/{plugin_id}/views/{view_id}")
async def open_view(plugin_id: str, view_id: str, manager: Host):
    return {"url": manager.open_view(plugin_id, view_id)}


@asset_router.get("/{ticket}/sdk.js")
async def ticket_sdk(ticket: str, manager: Host):
    manager.ticket_plugin(ticket)
    return FileResponse(
        Path(__file__).parents[2] / "plugins" / "frontend-sdk.js",
        media_type="text/javascript",
        headers=ASSET_HEADERS,
    )


@asset_router.get("/{ticket}/{plugin_id}/assets/{filename:path}")
async def ticket_asset(ticket: str, plugin_id: str, filename: str, manager: Host):
    if manager.ticket_plugin(ticket) != plugin_id:
        raise PluginError("View ticket is scoped to another plugin", 404)
    path = manager.asset(plugin_id, filename)
    return FileResponse(
        path,
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        headers=ASSET_HEADERS,
    )
