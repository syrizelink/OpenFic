"""
OpenFic Backend - FastAPI Application Entry Point.
"""

import asyncio
from contextlib import asynccontextmanager, suppress
import ipaddress
from os import getenv
from pathlib import Path
import socket
import sys
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

from app.api.exceptions import register_exception_handlers
from app.api.middleware import AccessLogMiddleware
from app.api.routers import (
    agent_definitions,
    agent_memories,
    agent_rules,
    agent_runtime,
    audit,
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
    settings,
    skill_reference_docs,
    skills,
    tasks,
    volumes,
    world_info,
    world_info_entries,
)
from app.audit import start_audit_queue, stop_audit_queue
from app.audit.queue import load_audit_details_persistence
from app.agent_runtime.runner.checkpointer import close_checkpointer, init_checkpointer
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.background.runtime.supervisor import (
    start_background_runtime,
    stop_background_runtime,
)
from app.core.storage import ensure_character_images_dir, ensure_covers_dir
from app.models.builtin import seed_builtin_models
from app.models.catalog import ModelProviderCatalogService
from app.settings import settings as app_settings
from app.socket import init_socketio
from app.storage.database import close_db, create_session, init_db
from app.storage.services import task_service


ANSI_BOLD = "\033[1m"
ANSI_GREEN = "\033[32m"
ANSI_BLUE = "\033[34m"
ANSI_RESET = "\033[0m"


def _resolve_frontend_dist_dir() -> Path:
    """解析前端构建产物目录。

    优先级：OPENFIC_FRONTEND_DIST 环境变量 > 打包内置路径 > 开发态相对路径。
    """
    env_dist = getenv("OPENFIC_FRONTEND_DIST")
    if env_dist:
        return Path(env_dist)

    packaged = Path(__file__).resolve().parents[1] / "frontend"
    if (packaged / "index.html").exists():
        return packaged

    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


FRONTEND_DIST_DIR = _resolve_frontend_dist_dir()


class SPAStaticFiles(StaticFiles):
    """Serve the frontend build and fall back to index.html for client routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


async def _reset_task_running_state() -> int:
    session = await create_session()
    try:
        cleared = await task_service.clear_running_tasks(session)
        await session.commit()
        return cleared
    finally:
        await session.close()


async def _seed_builtin_models() -> None:
    session = await create_session()
    try:
        await seed_builtin_models(session)
    finally:
        await session.close()


def _get_server_bind() -> tuple[str, int]:
    host = getenv("OPENFIC_SERVER_HOST", app_settings.host)
    port = int(getenv("OPENFIC_SERVER_PORT", str(app_settings.port)))
    return host, port


def _list_network_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            primary_ip = sock.getsockname()[0]
            if primary_ip and not primary_ip.startswith("127."):
                addresses.add(primary_ip)
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            if family != socket.AF_INET:
                continue
            ip = sockaddr[0]
            if isinstance(ip, str) and ip and not ip.startswith("127."):
                addresses.add(ip)
    except OSError:
        pass

    return sorted(addresses)


def _build_access_urls(host: str, port: int) -> list[tuple[str, str]]:
    try:
        parsed_host = ipaddress.ip_address(host)
    except ValueError:
        parsed_host = None

    if host == "localhost" or (parsed_host is not None and parsed_host.is_loopback):
        return [("Local", f"http://127.0.0.1:{port}")]

    if host == "0.0.0.0":
        urls: list[tuple[str, str]] = [("Local", f"http://127.0.0.1:{port}")]
        urls.extend(("Network", f"http://{ip}:{port}") for ip in _list_network_ipv4_addresses())
        return urls

    return [("Network", f"http://{host}:{port}")]


def _format_access_url_lines(host: str, port: int) -> list[str]:
    urls = _build_access_urls(host, port)
    label_width = max(len(label) for label, _ in urls)
    return [f"> {label:<{label_width}}: {url}" for label, url in urls]


def _supports_styled_banner_output() -> bool:
    stdout = sys.stdout
    if not hasattr(stdout, "isatty") or not stdout.isatty():
        return False
    if getenv("NO_COLOR"):
        return False
    return getenv("TERM") != "dumb"


def _bold(text: str) -> str:
    return f"{ANSI_BOLD}{text}{ANSI_RESET}"


def _bold_color(text: str, color: str) -> str:
    return f"{ANSI_BOLD}{color}{text}{ANSI_RESET}"


def _style_title_line(version: str, supports_ansi: bool) -> str:
    if not supports_ansi:
        return f"OpenFic v{version} - Entering the vibe writing era"
    return (
        f"{_bold_color('OpenFic', ANSI_GREEN)}"
        f"{ANSI_BOLD} v{version} - Entering the vibe writing era{ANSI_RESET}"
    )


def _style_link_line(url: str, supports_ansi: bool) -> str:
    if not supports_ansi:
        return url
    return _bold_color(url, ANSI_BLUE)


def _style_access_line(line: str, supports_ansi: bool) -> str:
    if not supports_ansi:
        return line

    prefix, url = line.split(": ", 1)
    return f"{ANSI_BOLD}{prefix}: {ANSI_BLUE}{url}{ANSI_RESET}"


def _format_banner_lines(version: str, host: str, port: int, supports_ansi: bool) -> list[str]:
    return [
        "",
        " ██████╗ ██████╗ ███████╗███╗   ██╗███████╗██╗ ██████╗",
        "██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔════╝██║██╔════╝",
        "██║   ██║██████╔╝█████╗  ██╔██╗ ██║█████╗  ██║██║     ",
        "██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██╔══╝  ██║██║     ",
        "╚██████╔╝██║     ███████╗██║ ╚████║██║     ██║╚██████╗",
        " ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚═╝     ╚═╝ ╚═════╝",
        "",
        _style_title_line(version, supports_ansi),
        "",
        _style_link_line("https://github.com/syrizelink/OpenFic", supports_ansi),
        "",
        *[_style_access_line(line, supports_ansi) for line in _format_access_url_lines(host, port)],
        "",
    ]


def _print_startup_banner(version: str) -> None:
    """启动完成后输出不含日志格式前缀的 banner。"""
    host, port = _get_server_bind()
    lines = _format_banner_lines(
        version=version,
        host=host,
        port=port,
        supports_ansi=_supports_styled_banner_output(),
    )
    print("\n".join(lines), flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    logger.info(f"Starting {app_settings.app_name} v{app_settings.app_version}")
    await init_db()
    cleared_tasks = await _reset_task_running_state()
    if cleared_tasks:
        logger.warning(f"已重置 {cleared_tasks} 个遗留的运行中任务状态")
    await _seed_builtin_models()
    await init_checkpointer()
    await load_audit_details_persistence()
    start_audit_queue()
    await start_background_runtime()
    _print_startup_banner(app_settings.app_version)
    catalog_refresh_task = asyncio.create_task(
        ModelProviderCatalogService().refresh(),
        name="model-provider-catalog-refresh",
    )
    try:
        yield
    finally:
        logger.info(f"Shutting down {app_settings.app_name}")
        if not catalog_refresh_task.done():
            catalog_refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await catalog_refresh_task
        cancelled_runs = await get_agent_run_registry().cancel_all()
        if cancelled_runs:
            logger.info(f"已取消 {cancelled_runs} 个运行中的 Agent 任务")
        cleared_tasks = await _reset_task_running_state()
        if cleared_tasks:
            logger.info(f"已清理 {cleared_tasks} 个任务的运行状态")
        await stop_background_runtime()
        await stop_audit_queue()
        await app.state.catalog_icon_proxy_service.aclose()
        await close_checkpointer()
        await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    app.state.catalog_icon_proxy_service = model_icons.CatalogIconProxyService()

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AccessLogMiddleware)

    # Mount routers
    app.include_router(health.router, prefix=app_settings.api_v1_prefix)
    app.include_router(projects.router, prefix=app_settings.api_v1_prefix)
    app.include_router(volumes.router, prefix=app_settings.api_v1_prefix)
    app.include_router(chapters.router, prefix=app_settings.api_v1_prefix)
    app.include_router(notes.router, prefix=app_settings.api_v1_prefix)
    app.include_router(characters.router, prefix=app_settings.api_v1_prefix)
    app.include_router(world_info.router, prefix=app_settings.api_v1_prefix)
    app.include_router(world_info_entries.router, prefix=app_settings.api_v1_prefix)
    app.include_router(settings.router, prefix=app_settings.api_v1_prefix)
    app.include_router(import_router.router, prefix=app_settings.api_v1_prefix)
    app.include_router(model_providers.router, prefix=app_settings.api_v1_prefix)
    app.include_router(model_provider_catalog.router, prefix=app_settings.api_v1_prefix)
    app.include_router(models.router, prefix=app_settings.api_v1_prefix)
    app.include_router(prompt_chains.router, prefix=app_settings.api_v1_prefix)
    app.include_router(agent_definitions.router, prefix=app_settings.api_v1_prefix)
    app.include_router(retrieval_index.router, prefix=app_settings.api_v1_prefix)
    app.include_router(retrieval_index.global_router, prefix=app_settings.api_v1_prefix)
    app.include_router(skills.router, prefix=app_settings.api_v1_prefix)
    app.include_router(skill_reference_docs.router, prefix=app_settings.api_v1_prefix)
    app.include_router(agent_rules.router, prefix=app_settings.api_v1_prefix)
    app.include_router(agent_memories.router, prefix=app_settings.api_v1_prefix)
    app.include_router(chapter_context.router, prefix=app_settings.api_v1_prefix)
    app.include_router(tasks.router, prefix=app_settings.api_v1_prefix)
    app.include_router(
        agent_runtime.router, prefix=f"{app_settings.api_v1_prefix}/agent"
    )
    app.include_router(audit.router, prefix=app_settings.api_v1_prefix)
    app.include_router(background.router, prefix=app_settings.api_v1_prefix)
    app.include_router(dashboard.router, prefix=app_settings.api_v1_prefix)
    app.include_router(model_icons.router)

    # 挂载静态文件服务（封面图片）
    covers_dir = ensure_covers_dir()
    app.mount("/covers", StaticFiles(directory=str(covers_dir)), name="covers")

    character_images_dir = ensure_character_images_dir()
    app.mount(
        "/character-images",
        StaticFiles(directory=str(character_images_dir)),
        name="character_images",
    )

    # 挂载前端构建产物；开发环境未构建时跳过，避免后端启动失败。
    if (FRONTEND_DIST_DIR / "index.html").exists():
        app.mount(
            "/",
            SPAStaticFiles(directory=str(FRONTEND_DIST_DIR), html=True),
            name="frontend",
        )
    else:
        logger.info(f"Frontend build not found, skip static mount: {FRONTEND_DIST_DIR}")

    # 注册全局异常处理器
    register_exception_handlers(app)

    return app


fastapi_app = create_app()
asgi_app = init_socketio(fastapi_app)
app = asgi_app
