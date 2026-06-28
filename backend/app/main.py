"""
OpenFic Backend - FastAPI Application Entry Point.
"""

from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path
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
from app.agent_runtime.audit.queue import start_audit_queue, stop_audit_queue
from app.agent_runtime.runner.checkpointer import close_checkpointer, init_checkpointer
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.background.runtime.supervisor import (
    start_background_runtime,
    stop_background_runtime,
)
from app.core.storage import ensure_covers_dir
from app.models.builtin import seed_builtin_models
from app.settings import settings as app_settings
from app.socket import init_socketio
from app.storage.database import close_db, create_session, init_db
from app.storage.services import task_service


def _resolve_frontend_dist_dir() -> Path:
    """解析前端构建产物目录。

    优先级：OPENFIC_FRONTEND_DIST 环境变量 > 打包内置路径 > 开发态相对路径。
    """
    env_dist = getenv("OPENFIC_FRONTEND_DIST")
    if env_dist:
        return Path(env_dist)

    packaged = Path(__file__).resolve().parent / "frontend_dist"
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
    start_audit_queue()
    await start_background_runtime()
    yield
    logger.info(f"Shutting down {app_settings.app_name}")
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

    # 挂载静态文件服务（模型图标）
    icons_dir = app_settings.static_dir / "icons" / "model"
    icons_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/icons/model", StaticFiles(directory=str(icons_dir)), name="model_icons")

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
