"""Authenticated extension management and versioned plugin RPC transport."""

import asyncio
import io
import json
import mimetypes
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    Response,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from loguru import logger
from pydantic import (
    JsonValue,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    ValidationInfo,
)
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.plugins.host import InstallProgress, InstallStage, PluginError, PluginHost
from app.plugins.manifest import (
    API_VERSION,
    MAX_PACKAGE_BYTES,
    SDK_VERSION,
    UI_SLOTS,
    CAPABILITIES,
)
from app.plugins.repository import download_repository, RepositoryDownloadError
from app.storage.database import get_session
from app.socket import emitter
from app.socket.handlers import (
    PLUGIN_INSTALL_PROGRESS_EVENT,
    PLUGIN_INSTALL_ROOM_PREFIX,
    plugin_install_snapshots,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])
asset_router = APIRouter(prefix="/plugin-assets", tags=["plugin views"])
oauth_router = APIRouter(prefix="/plugin-oauth", tags=["plugin OAuth"])


ASSET_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; media-src 'self' blob:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'",
}
DETAIL_HEADERS = {
    **ASSET_HEADERS,
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox",
}


def host(request: Request) -> PluginHost:
    return request.app.state.plugin_host


Host = Annotated[PluginHost, Depends(host)]


async def plugin_exception_handler(request: Request, error: Exception):
    # The access log already records status/path. Do not dump plugin command
    # frames, which may contain OAuth tokens or other private settings.
    assert isinstance(error, PluginError)
    return JSONResponse(
        status_code=error.status_code, content={"detail": str(error.detail)}
    )


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


class EditorEventRequest(BaseModel):
    event: Literal["editor.change"]
    data: dict[str, Any]


@router.post("/events/dispatch")
async def dispatch_editor_event(
    payload: EditorEventRequest,
    manager: Host,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from app.plugins.runtime import dispatch
    from app.plugins.services import bounded_json

    value = bounded_json(payload.data)
    try:
        return {
            "data": await dispatch(
                payload.event,
                value,
                session,
                host=manager,
                runtime={"project_id": value.get("projectId")},
            )
        }
    except Exception as error:
        raise PluginError(str(error), 422) from error


class ConfigurationRequest(BaseModel):
    settings: dict[str, Any]


class CallRequest(BaseModel):
    method: str = Field(min_length=1, max_length=80)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def bounded_params(
        cls, value: dict[str, Any], info: ValidationInfo
    ) -> dict[str, Any]:
        limit = (
            4 * 1024 * 1024
            if info.data.get("method", "").startswith("sdk.")
            else 64_000
        )
        if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > limit:
            raise ValueError(f"RPC parameters exceed {limit} bytes")
        return value


def require_trust(trusted: bool) -> None:
    if not trusted:
        raise PluginError("Installation requires acknowledging trusted-code execution")


async def read_package(file: UploadFile, trusted: bool) -> bytes:
    require_trust(trusted)
    content = await file.read(MAX_PACKAGE_BYTES + 1)
    if len(content) > MAX_PACKAGE_BYTES:
        raise PluginError("Package exceeds 20 MiB")
    return content


@contextmanager
def install_progress(operation_id: UUID | None) -> Iterator[InstallProgress | None]:
    if operation_id is None:
        yield None
        return
    if operation_id in plugin_install_snapshots:
        raise PluginError("Installation operation is already in progress", 409)
    plugin_install_snapshots[operation_id] = None

    async def report(stage: InstallStage, progress: int) -> None:
        payload: dict[str, str | int] = {
            "operation_id": str(operation_id),
            "stage": stage,
            "progress": progress,
        }
        plugin_install_snapshots[operation_id] = payload
        try:
            async with asyncio.timeout(1):
                await emitter.emit(
                    PLUGIN_INSTALL_PROGRESS_EVENT,
                    payload,
                    room=f"{PLUGIN_INSTALL_ROOM_PREFIX}{operation_id}",
                )
        except Exception:
            logger.debug("Plugin install progress could not be sent: {}", operation_id)

    try:
        yield report
    finally:
        plugin_install_snapshots.pop(operation_id, None)


class RepositoryInstall(BaseModel):
    url: str = Field(max_length=256)
    trusted: bool = False
    operation_id: UUID | None = None


@router.get("")
async def list_plugins(manager: Host):
    return {
        "api_version": API_VERSION,
        "sdk_version": SDK_VERSION,
        "slots": UI_SLOTS,
        "plugins": [manager.describe(p) for p in manager.plugins.values()],
    }


class PluginOrder(BaseModel):
    plugin_ids: list[str]


@router.put("/order")
async def update_plugin_order(payload: PluginOrder, manager: Host) -> PluginOrder:
    try:
        return PluginOrder(plugin_ids=await manager.set_order(payload.plugin_ids))
    except ValueError as error:
        raise PluginError(str(error)) from error


@router.get("/development")
async def development_status(manager: Host):
    return (
        manager.development.describe()
        if manager.development
        else {"enabled": False, "inspector": manager.diagnostics.enabled}
    )


@router.post("/development/reload")
async def reload_development(manager: Host):
    if not manager.development:
        raise PluginError("Plugin development is not enabled", 404)
    return await manager.development.reload()


@router.get("/{plugin_id}/inspector")
async def inspector(plugin_id: str, manager: Host):
    manager.get(plugin_id)
    if not manager.diagnostics.enabled:
        raise PluginError("Plugin Inspector is not enabled", 404)
    return manager.diagnostics.snapshot(plugin_id)


class FrontendDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pluginId: str
    viewId: str | None = None
    kind: Literal["render", "action", "effect", "iframe"]
    method: str = Field(max_length=128)
    status: Literal["ok", "error"]
    durationMs: float = Field(default=0, ge=0, le=3600000)
    request: JsonValue = None
    result: JsonValue = None
    error: JsonValue = None

    @field_validator("request", "result", "error")
    @classmethod
    def bounded_payload(cls, value):
        if len(json.dumps(value, allow_nan=False).encode()) > 64000:
            raise ValueError("Diagnostic payload exceeds 64 KiB")
        return value


@router.post("/{plugin_id}/inspector/report", status_code=204)
async def report_frontend_diagnostic(
    plugin_id: str, data: FrontendDiagnostic, manager: Host
):
    plugin = manager.get(plugin_id)
    if not manager.diagnostics.enabled:
        raise PluginError("Plugin Inspector is not enabled", 404)
    if (
        data.pluginId != plugin_id
        or data.viewId
        and data.viewId not in {view.id for view in plugin.manifest.views}
    ):
        raise PluginError("Invalid diagnostic plugin/view identity", 422)
    manager.diagnostics.add(
        plugin,
        "frontend." + data.kind,
        data.method,
        data.request,
        data.result,
        data.error if data.status == "error" else None,
        data.durationMs / 1000,
        view_id=data.viewId,
    )
    return Response(status_code=204)


@router.delete("/{plugin_id}/inspector")
async def clear_inspector(plugin_id: str, manager: Host):
    manager.get(plugin_id)
    if not manager.diagnostics.enabled:
        raise PluginError("Plugin Inspector is not enabled", 404)
    manager.diagnostics.clear(plugin_id)
    return {"ok": True}


@router.get("/catalogue")
async def sdk_catalogue():
    from app.plugins.declarative import CATALOGUE
    from app.plugins.gateway import BusinessAPI
    from app.plugins.runtime import EVENTS

    return {
        "version": SDK_VERSION,
        "capabilities": sorted(CAPABILITIES),
        "slots": UI_SLOTS,
        "events": sorted(EVENTS),
        "ui": CATALOGUE,
        **BusinessAPI.catalogue(),
    }


@router.post("", status_code=201)
async def install_plugin(
    manager: Host,
    file: Annotated[UploadFile, File()],
    trusted: Annotated[bool, Form()] = False,
    operation_id: Annotated[UUID | None, Form()] = None,
):
    with install_progress(operation_id) as progress:
        return await manager.install(
            await read_package(file, trusted), progress=progress
        )


@router.post("/repository", status_code=201)
async def install_repository(payload: RepositoryInstall, manager: Host):
    require_trust(payload.trusted)
    with install_progress(payload.operation_id) as progress:
        try:
            content = await download_repository(payload.url, progress)
        except RepositoryDownloadError as error:
            status = {
                "invalid": 422,
                "not_found": 404,
                "too_large": 413,
                "timeout": 504,
                "upstream": 502,
            }
            raise PluginError(str(error), status[error.kind]) from error
        return await manager.install(
            content, repository_archive=True, progress=progress
        )


@router.get("/sdk.js")
async def frontend_sdk():
    return FileResponse(
        Path(__file__).parents[2] / "plugins" / "frontend-sdk.js",
        media_type="text/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/sdk.d.ts")
async def frontend_types():
    return FileResponse(
        Path(__file__).parents[2] / "plugins" / "sdk.d.ts", media_type="text/plain"
    )


@router.put("/{plugin_id}/package")
async def update_plugin(
    plugin_id: str,
    manager: Host,
    file: Annotated[UploadFile, File()],
    trusted: Annotated[bool, Form()] = False,
    operation_id: Annotated[UUID | None, Form()] = None,
):
    with install_progress(operation_id) as progress:
        return await manager.install(
            await read_package(file, trusted), update_id=plugin_id, progress=progress
        )


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


class PluginLogEntry(BaseModel):
    time: str
    level: str
    action: str
    message: str


@router.get("/{plugin_id}/logs", response_model=list[PluginLogEntry])
async def plugin_logs(
    plugin_id: str,
    manager: Host,
    minutes: Annotated[int | None, Query(gt=0, le=1440)] = None,
    limit: Annotated[int | None, Query(gt=0, le=1000)] = None,
):
    return await run_in_threadpool(manager.logs, plugin_id, minutes, limit)


@router.get("/{plugin_id}/logs/download")
async def download_plugin_logs(plugin_id: str, manager: Host):
    manager.get(plugin_id)

    def lines() -> Iterator[str]:
        for entry in manager.iter_logs(plugin_id):
            yield f"{entry['time']} [{entry['level']}] {entry['action']}: {entry['message']}\n"

    return StreamingResponse(
        lines(),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{plugin_id}.log"'},
    )


@router.delete("/{plugin_id}/logs", status_code=204)
async def clear_plugin_logs(plugin_id: str, manager: Host) -> Response:
    manager.clear_logs(plugin_id)
    return Response(status_code=204)


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


@router.get("/{plugin_id}/detail")
async def plugin_detail(plugin_id: str, manager: Host):
    return FileResponse(
        manager.detail_file(plugin_id),
        media_type="text/plain",
        headers=DETAIL_HEADERS,
    )


@router.get("/{plugin_id}/icon")
async def plugin_icon(plugin_id: str, manager: Host):
    data, media_type = await asyncio.to_thread(manager.icon_data, plugin_id)
    return Response(data, media_type=media_type, headers=DETAIL_HEADERS)


@router.get("/{plugin_id}/detail-images/{filename:path}")
async def plugin_detail_image(plugin_id: str, filename: str, manager: Host):
    path = manager.detail_file(plugin_id, filename)
    return FileResponse(
        path,
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        headers=DETAIL_HEADERS,
    )


@router.post("/{plugin_id}/views/{view_id}")
async def open_view(plugin_id: str, view_id: str, manager: Host):
    return {"url": manager.open_view(plugin_id, view_id)}


class ViewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: dict[str, Any] = Field(default_factory=dict)
    columns: int = Field(default=100, ge=20, le=240)
    id: str = Field(default="", max_length=128)
    event: Literal[
        "press", "input", "submit", "select", "change", "command", "close"
    ] = "press"
    value: JsonValue = None

    @field_validator("context", "value")
    @classmethod
    def bounded(cls, value):
        if len(json.dumps(value, allow_nan=False).encode()) > 64_000:
            raise ValueError("UI request exceeds 64 KiB")
        return value


@router.post("/{plugin_id}/views/{view_id}/{operation}")
async def declarative_view(
    plugin_id: str,
    view_id: str,
    operation: Literal["render", "action"],
    data: ViewRequest,
    manager: Host,
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    from app.plugins.declarative import validate_document

    plugin = manager.get(plugin_id)
    view = next((v for v in plugin.manifest.views if v.id == view_id), None)
    if view is None or view.renderer != "declarative":
        raise PluginError("Declarative view is unavailable", 404)
    if "ui" not in plugin.manifest.capabilities:
        raise PluginError("Plugin has not declared ui", 403)
    method = view.render if operation == "render" else view.action
    assert method is not None
    params = {**data.model_dump(), "slot": view.slot, "viewId": view.id}
    result = await manager.call(
        plugin_id,
        method,
        params,
        session,
        runtime={
            "backend_url": str(request.base_url).rstrip("/"),
            "project_id": data.context.get("projectId"),
        },
    )
    if operation == "action":
        return {"result": result}
    try:
        return validate_document(result, capabilities=plugin.manifest.capabilities)
    except (ValueError, KeyError, TypeError) as error:
        raise PluginError(f"Invalid declarative UI: {error}", 422) from error


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
    plugin = manager.get(plugin_id)
    if any(
        view.entry and plugin.manifest.resource_url_name(view.entry) == filename
        for view in plugin.manifest.views
    ):
        from app.plugins.html import inject_sdk

        return HTMLResponse(
            inject_sdk(
                path.read_text(encoding="utf-8-sig"), f"/plugin-assets/{ticket}/sdk.js"
            ),
            headers=ASSET_HEADERS,
        )
    return FileResponse(
        path,
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        headers=ASSET_HEADERS,
    )
