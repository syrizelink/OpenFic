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
import time
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
    auth,
    agent_definitions,
    agent_memories,
    agent_rules,
    agent_runtime,
    audit,
    background,
    characters,
    chapter_context,
    chapter_exports,
    chapters,
    commands,
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
    runtime_config,
    settings,
    skill_reference_docs,
    skills,
    tasks,
    volumes,
    world_info,
    world_info_entries,
)
from app.auth import AuthMiddleware, AuthService
from app.audit import start_audit_queue, stop_audit_queue
from app.agent_runtime.persistence.child_runs import cancel_interrupted_child_runs
from app.audit.queue import load_audit_details_persistence
from app.telemetry import (
    SETTING_KEY_TELEMETRY_ENABLED,
    install_telemetry_sink,
    parse_telemetry_enabled,
    set_telemetry_enabled,
    shutdown as shutdown_telemetry,
)
from app.agent_runtime.runner.checkpointer import (
    checkpoint_free_page_bytes,
    cleanup_unreachable_checkpoints,
    close_checkpointer,
    full_vacuum_checkpoint_database,
    get_checkpointer,
    init_checkpointer,
    migrate_checkpoint_database_to_incremental,
    needs_incremental_auto_vacuum_migration,
    prune_reachable_checkpoints,
)
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.background.runtime.supervisor import (
    start_background_runtime,
    stop_background_runtime,
)
from app.agent_runtime.attachments import (
    cleanup_orphaned_agent_attachment_files,
    ensure_agent_attachments_dir,
)
from app.core.storage import ensure_character_images_dir, ensure_covers_dir
from app.chapter_export.service import cleanup_chapter_export_files
from app.models.builtin import seed_builtin_models
from app.models.catalog import ModelProviderCatalogService
from app.maintenance import maintenance_state
from app.settings import settings as app_settings
from app.socket import init_socketio
from app.storage.database import close_db, create_session, init_db, vacuum_database_if_needed
from app.storage.repos import revision_repo, setting_repo
from app.storage.services import task_service
from app.storage.services.revision_content_backfill import backfill_revision_content_blobs
from app.storage.services.revision_service import cleanup_orphaned_revision_data


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


async def _reset_active_revision_state() -> int:
    session = await create_session()
    try:
        recovered = await revision_repo.recover_active_revisions_for_stopped_tasks(session)
        await session.commit()
        return recovered
    finally:
        await session.close()


async def _reset_interrupted_child_run_state() -> int:
    session = await create_session()
    try:
        cancelled = await cancel_interrupted_child_runs(session)
        await session.commit()
        return cancelled
    finally:
        await session.close()


async def _load_telemetry_enabled() -> None:
    session = await create_session()
    try:
        setting = await setting_repo.get_by_key(session, SETTING_KEY_TELEMETRY_ENABLED)
        set_telemetry_enabled(
            parse_telemetry_enabled(setting.value if setting else None)
        )
    finally:
        await session.close()


async def _seed_builtin_models() -> None:
    session = await create_session()
    try:
        await seed_builtin_models(session)
    finally:
        await session.close()


async def _cleanup_unreachable_checkpoints() -> int:
    session = await create_session()
    try:
        checkpointer = await get_checkpointer()
        deleted_rows = await cleanup_unreachable_checkpoints(session, checkpointer)
        deleted_rows += await prune_reachable_checkpoints(session, checkpointer)
    finally:
        await session.close()

    if deleted_rows:
        logger.info(f"Deleted {deleted_rows} checkpoint rows during startup cleanup")
    return deleted_rows


_vacuum_started_at: float | None = None
_migrate_started_at: float | None = None
_backfill_started_at: float | None = None


def _emit_single_line_progress(message: str) -> None:
    """输出维护进度行。以换行结尾，保证桌面端能实时按行解析。"""
    sys.stdout.write(f"{message}\n")
    sys.stdout.flush()


def _update_checkpoint_maintenance_progress(
    phase: str,
    progress: float | None,
    reclaimed_pages: int,
    total_pages: int,
) -> None:
    global _vacuum_started_at, _migrate_started_at
    maintenance_state.update(
        phase=phase,
        message=(
            "Migrating checkpoint database to incremental auto-vacuum."
            if phase == "migrating"
            else "Reclaiming freed checkpoint pages."
        ),
        progress=progress,
        reclaimed_pages=reclaimed_pages,
        total_pages=total_pages,
    )
    if phase == "migrating":
        if _migrate_started_at is None:
            _migrate_started_at = time.monotonic()
        ops_label = f"{reclaimed_pages:,}" if reclaimed_pages else "..."
        elapsed = time.monotonic() - _migrate_started_at
        _emit_single_line_progress(
            f"[maintenance] Migrating checkpoint database: "
            f"{ops_label} VM ops, {elapsed:.1f}s elapsed"
        )
    elif phase == "vacuuming" and progress is None:
        if _vacuum_started_at is None:
            _vacuum_started_at = time.monotonic()
        elapsed = time.monotonic() - _vacuum_started_at
        ops_label = f"{reclaimed_pages:,}" if reclaimed_pages else "..."
        _emit_single_line_progress(
            f"[maintenance] Compacting checkpoint database: "
            f"{ops_label} VM ops, {elapsed:.1f}s elapsed"
        )
    elif progress is not None:
        percent = progress * 100
        if phase == "vacuuming":
            if _vacuum_started_at is None:
                _vacuum_started_at = time.monotonic()
            elapsed = time.monotonic() - _vacuum_started_at
            size_gb = reclaimed_pages / (1024**3)
            _emit_single_line_progress(
                f"[maintenance] Compacting checkpoint database: "
                f"{size_gb:.1f}/{total_pages / (1024**3):.1f}GB ({percent:.1f}%), {elapsed:.1f}s"
            )
        else:
            _emit_single_line_progress(
                f"[maintenance] Reclaiming freed checkpoint pages: "
                f"{reclaimed_pages}/{total_pages} ({percent:.1f}%)"
            )


async def _run_startup_maintenance() -> None:
    global _vacuum_started_at, _migrate_started_at
    maintenance_state.start()
    logger.info("Local database maintenance started")
    try:
        maintenance_state.update(
            phase="pruning",
            message="Pruning obsolete checkpoints.",
            progress=None,
        )
        deleted_rows = await _cleanup_unreachable_checkpoints()
        maintenance_state.update(
            phase="pruning",
            message="Checkpoint pruning completed.",
            progress=None,
            deleted_rows=deleted_rows,
        )

        await close_checkpointer()

        # 阶段 1：必要时迁移到 INCREMENTAL（普通 VACUUM，set_progress_handler 监控 VM 操作数）
        if await needs_incremental_auto_vacuum_migration():
            maintenance_state.update(
                phase="migrating",
                message="Migrating checkpoint database to incremental auto-vacuum.",
                progress=None,
            )
            logger.info("Migrating checkpoint database to incremental auto-vacuum")
            _migrate_started_at = time.monotonic()
            await migrate_checkpoint_database_to_incremental(
                progress_callback=_update_checkpoint_maintenance_progress,
            )
            logger.info(
                f"Migrated checkpoint database to incremental auto-vacuum in "
                f"{time.monotonic() - _migrate_started_at:.1f}s"
            )
            _migrate_started_at = None
        else:
            logger.info("Checkpoint database already uses incremental auto-vacuum, skipping migration")

        # 阶段 2：空页达到阈值才执行 VACUUM INTO 回收
        free_bytes, live_bytes = await checkpoint_free_page_bytes()
        free_ratio = free_bytes / live_bytes if live_bytes > 0 else 0.0
        should_vacuum = free_bytes > 1024**3 or free_ratio > 0.3
        if should_vacuum:
            maintenance_state.update(
                phase="vacuuming",
                message="Reclaiming freed checkpoint pages.",
                progress=None,
            )
            logger.info(
                f"Reclaiming checkpoint free space: {free_bytes / (1024**3):.1f}GB free "
                f"({free_ratio * 100:.0f}% of live data)"
            )
            await full_vacuum_checkpoint_database(
                progress_callback=_update_checkpoint_maintenance_progress,
            )
        else:
            logger.info(
                f"Checkpoint free space below threshold, skipping vacuum "
                f"({free_bytes / (1024**3):.1f}GB free, {free_ratio * 100:.0f}% of live data)"
            )

        maintenance_state.update(
            phase="cleanup",
            message="Cleaning auxiliary local data.",
            progress=None,
        )
        await init_checkpointer()

        await _cleanup_chapter_export_files()
        await _cleanup_orphaned_agent_attachment_files()
        await _cleanup_orphaned_task_data()
        await _cleanup_orphaned_revision_data()
        await _backfill_revision_content()
        await _vacuum_main_database()
        await start_background_runtime()
        maintenance_state.complete()
        logger.info(
            "Local database maintenance completed"
            + (
                f", vacuum took {time.monotonic() - _vacuum_started_at:.1f}s"
                if _vacuum_started_at is not None
                else ""
            )
        )
        _vacuum_started_at = None
    except Exception as exc:
        message = _friendly_maintenance_error(exc)
        logger.error("Local database maintenance failed: %s", message)
        maintenance_state.fail(message)
        await _restore_checkpointer_and_runtime()


def _friendly_maintenance_error(exc: Exception) -> str:
    """将底层异常转换为对用户友好的维护失败说明。"""
    text = str(exc).lower()
    if "disk" in text or "space" in text or "full" in text:
        return (
            "磁盘空间不足，无法重整本地数据库。"
            "请释放磁盘空间后重新启动应用重试。"
        )
    return f"本地数据库维护失败：{exc}"


async def _restore_checkpointer_and_runtime() -> None:
    """Best-effort recovery so a failed maintenance does not leave the backend degraded."""
    try:
        await init_checkpointer()
        await start_background_runtime()
    except Exception:
        logger.exception(
            "Failed to restore checkpointer/background runtime after maintenance failure"
        )


async def _cleanup_chapter_export_files() -> None:
    session = await create_session()
    try:
        deleted_files = await cleanup_chapter_export_files(session)
        if deleted_files:
            logger.info(f"Deleted {deleted_files} expired or unreachable chapter export files")
    finally:
        await session.close()


async def _cleanup_orphaned_agent_attachment_files() -> None:
    session = await create_session()
    try:
        deleted_files = await cleanup_orphaned_agent_attachment_files(session)
        if deleted_files:
            logger.info(f"Deleted {deleted_files} orphaned agent attachment files at startup")
    finally:
        await session.close()


async def _cleanup_orphaned_task_data() -> None:
    session = await create_session()
    try:
        deleted_rows = await task_service.cleanup_orphaned_task_data(session)
        await session.commit()
        if deleted_rows:
            logger.info(f"Deleted {deleted_rows} orphaned task runtime rows at startup")
    finally:
        await session.close()


def _update_backfill_progress(
    phase: str,
    progress: float | None,
    processed: int,
    total: int,
) -> None:
    global _backfill_started_at
    maintenance_state.update(
        phase="backfilling",
        message="Backfilling revision content into compressed blobs.",
        progress=progress,
        deleted_rows=processed,
        total_pages=total,
    )
    if progress is None:
        _backfill_started_at = time.monotonic()
        _emit_single_line_progress(
            f"[maintenance] Backfilling revision content: {total:,} rows"
        )
        return
    if progress >= 1.0:
        if _backfill_started_at is None:
            _backfill_started_at = time.monotonic()
        elapsed = time.monotonic() - _backfill_started_at
        _backfill_started_at = None
        if processed == 0 and total == 0:
            _emit_single_line_progress(
                "[maintenance] Backfill already completed, skipping."
            )
        else:
            _emit_single_line_progress(
                f"[maintenance] Backfill completed: {processed:,} rows rewritten "
                f"in {elapsed:.1f}s"
            )
        return
    if _backfill_started_at is None:
        _backfill_started_at = time.monotonic()
    elapsed = time.monotonic() - _backfill_started_at
    percent = progress * 100
    _emit_single_line_progress(
        f"[maintenance] Backfilling revision content: {processed:,}/{total:,} "
        f"({percent:.1f}%), {elapsed:.1f}s"
    )


async def _cleanup_orphaned_revision_data() -> int:
    session = await create_session()
    try:
        deleted_rows = await cleanup_orphaned_revision_data(session)
        await session.commit()
        if deleted_rows:
            logger.info(f"Deleted {deleted_rows} orphaned revision rows at startup")
        return deleted_rows
    finally:
        await session.close()


async def _backfill_revision_content() -> int:
    session = await create_session()
    try:
        return await backfill_revision_content_blobs(
            session,
            progress_callback=_update_backfill_progress,
        )
    finally:
        await session.close()


async def _vacuum_main_database() -> None:
    await close_db()
    if await vacuum_database_if_needed():
        logger.info("Vacuumed main database after startup cleanup")


def _get_server_bind() -> tuple[str, int]:
    host = getenv("OPENFIC_SERVER_HOST")
    port = getenv("OPENFIC_SERVER_PORT")

    if host is None:
        host = _get_command_line_option("--host") or app_settings.host
    if port is None:
        port = _get_command_line_option("--port") or str(app_settings.port)

    return host, int(port)


def _get_command_line_option(option: str) -> str | None:
    option_with_value = f"{option}="
    for index, argument in enumerate(sys.argv):
        if argument.startswith(option_with_value):
            return argument.removeprefix(option_with_value)
        if argument == option and index + 1 < len(sys.argv):
            return sys.argv[index + 1]

    return None


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
    await _load_telemetry_enabled()
    cleared_tasks = await _reset_task_running_state()
    if cleared_tasks:
        logger.warning(f"已重置 {cleared_tasks} 个遗留的运行中任务状态")
    recovered_revisions = await _reset_active_revision_state()
    if recovered_revisions:
        logger.warning(f"已恢复 {recovered_revisions} 个遗留的 Agent revision 状态")
    cancelled_child_runs = await _reset_interrupted_child_run_state()
    if cancelled_child_runs:
        logger.warning(f"已取消 {cancelled_child_runs} 个因服务重启中断的子 Agent 任务")
    await _seed_builtin_models()
    await load_audit_details_persistence()
    start_audit_queue()
    await _run_startup_maintenance()
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
        cancelled_child_runs = await _reset_interrupted_child_run_state()
        if cancelled_child_runs:
            logger.info(f"已取消 {cancelled_child_runs} 个中断的子 Agent 任务")
        cleared_tasks = await _reset_task_running_state()
        if cleared_tasks:
            logger.info(f"已清理 {cleared_tasks} 个任务的运行状态")
        await stop_background_runtime()
        await stop_audit_queue()
        await app.state.catalog_icon_proxy_service.aclose()
        await close_checkpointer()
        await close_db()
        shutdown_telemetry()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    app.state.auth_service = AuthService(app_settings.auth_password)
    app.state.catalog_icon_proxy_service = model_icons.CatalogIconProxyService()

    install_telemetry_sink()

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AccessLogMiddleware)

    # Mount routers
    app.include_router(auth.router, prefix=app_settings.api_v1_prefix)
    app.include_router(health.router, prefix=app_settings.api_v1_prefix)
    app.include_router(runtime_config.router, prefix=app_settings.api_v1_prefix)
    app.include_router(projects.router, prefix=app_settings.api_v1_prefix)
    app.include_router(volumes.router, prefix=app_settings.api_v1_prefix)
    app.include_router(chapters.router, prefix=app_settings.api_v1_prefix)
    app.include_router(notes.router, prefix=app_settings.api_v1_prefix)
    app.include_router(commands.router, prefix=app_settings.api_v1_prefix)
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
    app.include_router(chapter_exports.router, prefix=app_settings.api_v1_prefix)
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

    agent_attachments_dir = ensure_agent_attachments_dir()
    app.mount(
        "/agent-attachments",
        StaticFiles(directory=str(agent_attachments_dir)),
        name="agent_attachments",
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
app = AuthMiddleware(
    asgi_app,
    fastapi_app.state.auth_service,
    app_settings.api_v1_prefix,
)
