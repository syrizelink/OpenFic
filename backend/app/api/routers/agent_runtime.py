# -*- coding: utf-8 -*-
"""Agent API Router - new agent_runtime-backed workflow."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeGuard, cast

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent_runtime.agents.definitions import load_agent_definition
from app.agent_runtime.context.compaction.service import CompactionError
from app.agent_runtime.persistence.child_runs import get_child_run_by_pending_approval
from app.agent_runtime.persistence.child_runs import (
    TERMINAL_CHILD_RUN_STATUSES,
    count_pending_child_run_requests,
    cancel_child_run,
    list_active_child_runs,
    list_child_runs_for_parent,
)
from app.agent_runtime.persistence.child_runs import get_child_run_agent_number
from app.agent_runtime.persistence.task_projection import (
    load_task_messages_for_agent_session,
)
from app.agent_runtime.persistence.model import AgentChildRun
from app.agent_runtime.revisions import rollback_revision_for_session
from app.agent_runtime.fork import fork_agent_session_at_revision
from app.agent_runtime.model_config import without_api_key
from app.agent_runtime.runner.checkpointer import (
    delete_checkpoints_after_for_thread,
    delete_checkpoints_for_thread,
)
from app.agent_runtime.runner.session_runner import SessionRunner
from app.agent_runtime.runner.subagent_runner import SubagentRunner
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.agent_runtime.tools import ToolRegistry
from app.agent_runtime.tools.impls.orchestration.common import ensure_child_processing
from app.api.schemas.agent import (
    AgentCancelPendingMessageRequest,
    AgentCancelPendingMessageResponse,
    AgentCancelResponse,
    AgentCompactionResponse,
    AgentForkRequest,
    AgentForkResponse,
    AgentPendingMessageResponse,
    AgentQuestionAnswerRequest,
    AgentRollbackRequest,
    AgentRollbackResponse,
    ActiveSubagentStateResponse,
    AgentSendMessageRequest,
    AgentSendMessageResponse,
    AgentSessionCreateRequest,
    AgentSessionCreateResponse,
    AgentSessionStateResponse,
    SubagentSessionResponse,
    AgentToolApprovalRequest,
    AgentToolMetadataResponse,
)
from app.core.encryption import EncryptionService
from app.core.errors import NotFoundError
from app.core.ids import generate_id
from app.models.repos import model_provider_repo, model_repo
from app.settings import settings
from app.background.jobs.session_title_jobs import enqueue_session_title_job
from app.background.jobs import service as background_service
from app.socket import emit
from app.socket.handlers import agent_session_room, background_project_room
from app.storage.database import get_session
from app.storage.models.chapter import Chapter
from app.storage.services import task_service

router = APIRouter(tags=["Agent"])

LEGACY_DEFAULT_AGENT_SESSION_TITLE = "Agent Session"
DEFAULT_AGENT_SESSION_TITLE_PREFIX = "New session - "
DEFAULT_AGENT_SESSION_TITLE_PATTERN = re.compile(
    r"^New session - \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
)

TOOL_DISPLAY_ORDER = {
    "ask_user": 0,
    "get_plan": 1,
    "list_plan": 2,
    "create_plan": 3,
    "update_plan": 4,
    "read_chapter": 5,
    "list_chapters": 6,
    "list_volumes": 7,
    "write_chapter": 8,
    "edit_chapter": 9,
    "delete_chapter": 10,
    "create_volume": 11,
    "edit_volume": 12,
    "delete_volume": 13,
    "move_chapter_to_volume": 14,
    "list_characters": 15,
    "read_character": 16,
    "create_character": 17,
    "edit_character": 18,
    "delete_character": 19,
    "list_world_entries": 20,
    "read_world_entry": 21,
    "create_world_entry": 22,
    "edit_world_entry": 23,
    "delete_world_entry": 24,
    "activate_skill": 25,
    "reference_skill": 26,
}

TOOL_DISPLAY_METADATA = {
    "ask_user": {
        "name": "Ask",
        "description": "向用户提问以获取继续执行所需的信息。",
    },
    "get_plan": {
        "name": "Get Plan",
        "description": "读取指定共享计划及其 Todo 列表。",
    },
    "list_plan": {
        "name": "List Plans",
        "description": "列出当前父子会话共享的全部计划。",
    },
    "create_plan": {
        "name": "Create Plan",
        "description": "创建一个共享计划并初始化 Todo 列表。",
    },
    "update_plan": {
        "name": "Update Plan",
        "description": "按旧 Todo 切片精确替换共享计划中的 Todo 列表。",
    },
    "read_chapter": {
        "name": "Read",
        "description": "读取指定章节内容供 Agent 参考。",
    },
    "list_chapters": {
        "name": "List",
        "description": "列出指定卷内章节供 Agent 定位上下文。",
    },
    "list_volumes": {
        "name": "List Volumes",
        "description": "列出项目卷信息供 Agent 定位章节。",
    },
    "write_chapter": {
        "name": "Write",
        "description": "在指定卷内创建章节。",
    },
    "edit_chapter": {
        "name": "Edit",
        "description": "精确替换现有章节的标题或正文片段。",
    },
    "delete_chapter": {
        "name": "Delete",
        "description": "删除指定章节。",
    },
    "create_volume": {
        "name": "Create Volume",
        "description": "在项目末尾创建新卷。",
    },
    "edit_volume": {
        "name": "Edit Volume",
        "description": "编辑指定卷的标题或说明。",
    },
    "delete_volume": {
        "name": "Delete Volume",
        "description": "删除指定卷。",
    },
    "move_chapter_to_volume": {
        "name": "Move Chapter",
        "description": "将指定章节移动到目标卷末尾。",
    },
    "list_characters": {
        "name": "List Characters",
        "description": "列出当前项目角色名称。",
    },
    "read_character": {
        "name": "Read Character",
        "description": "根据名称读取角色描述。",
    },
    "create_character": {
        "name": "Create Character",
        "description": "在当前项目中创建角色。",
    },
    "edit_character": {
        "name": "Edit Character",
        "description": "编辑角色的名称或描述。",
    },
    "delete_character": {
        "name": "Delete Character",
        "description": "删除指定角色。",
    },
    "list_world_entries": {
        "name": "List World Entries",
        "description": "列出当前项目世界书条目标题。",
    },
    "read_world_entry": {
        "name": "Read World Entry",
        "description": "根据标题读取世界书条目内容。",
    },
    "create_world_entry": {
        "name": "Create World Entry",
        "description": "在当前项目世界书中创建条目。",
    },
    "edit_world_entry": {
        "name": "Edit World Entry",
        "description": "编辑世界书条目的标题或内容。",
    },
    "delete_world_entry": {
        "name": "Delete World Entry",
        "description": "删除指定世界书条目。",
    },
    "activate_skill": {
        "name": "Activate Skill",
        "description": "获取指定技能的完整内容与参考文档列表。",
    },
    "reference_skill": {
        "name": "Reference Skill",
        "description": "读取指定技能的某个参考文档内容。",
    },
}


def _build_default_agent_session_title(created_at: datetime) -> str:
    timestamp = created_at.astimezone(UTC).isoformat(timespec="milliseconds")
    return f"{DEFAULT_AGENT_SESSION_TITLE_PREFIX}{timestamp.replace('+00:00', 'Z')}"


def _is_pending_agent_session_title(title: str) -> bool:
    return title == LEGACY_DEFAULT_AGENT_SESSION_TITLE or bool(
        DEFAULT_AGENT_SESSION_TITLE_PATTERN.fullmatch(title)
    )

_SESSION_RUNNERS: dict[str, SessionRunner] = {}


def _build_seed_state(
    *,
    session_id: str,
    task_id: str,
    project_id: str,
    model_config: dict,
    agent_key: str = "primary",
    current_revision_id: str | None = None,
) -> dict:
    return {
        "session_id": session_id,
        "task_id": task_id,
        "project_id": project_id,
        "model_config": without_api_key(model_config),
        "active_agent": None,
        "agent_key": agent_key,
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "user_request": "",
        "current_revision_id": current_revision_id,
        "messages": [],
    }


def _is_valid_model_config(model_config: object) -> TypeGuard[dict[str, object]]:
    if not isinstance(model_config, dict):
        return False
    max_context_tokens = model_config.get("max_context_tokens")
    return isinstance(max_context_tokens, int) and max_context_tokens > 0


def _build_subagent_state_response(
    *,
    child_run: AgentChildRun,
    queued_messages: int,
) -> ActiveSubagentStateResponse:
    agent_number = get_child_run_agent_number(child_run.metadata_json)
    return ActiveSubagentStateResponse(
        child_run_id=child_run.id,
        child_thread_id=child_run.child_thread_id,
        agent_key=child_run.agent_key,
        agent_number=agent_number,
        status=child_run.status,
        queued_messages=queued_messages,
        is_active=child_run.is_active,
        pending_approval=(
            dict(child_run.pending_approval_json)
            if child_run.pending_approval_json is not None
            else None
        ),
    )


async def _list_descendant_child_runs(
    session: AsyncSession,
    *,
    parent_session_id: str,
) -> list[AgentChildRun]:
    descendants: list[AgentChildRun] = []
    for row in await list_child_runs_for_parent(session, parent_session_id):
        descendants.extend(
            await _list_descendant_child_runs(
                session,
                parent_session_id=row.child_thread_id,
            )
        )
        descendants.append(row)
    return descendants


async def _cancel_subagent_session_tree(
    session: AsyncSession,
    *,
    root_session_id: str,
    status_publisher: SubagentRunner | None = None,
) -> None:
    descendants = await _list_descendant_child_runs(
        session,
        parent_session_id=root_session_id,
    )
    registry = get_agent_run_registry()

    session_ids_to_cancel: list[str] = []
    seen_session_ids: set[str] = set()
    for session_id in [*(row.child_thread_id for row in descendants), root_session_id]:
        if session_id in seen_session_ids:
            continue
        seen_session_ids.add(session_id)
        session_ids_to_cancel.append(session_id)

    for session_id in session_ids_to_cancel:
        await registry.cancel(session_id)

    for row in descendants:
        if not row.is_active:
            continue
        if row.status in TERMINAL_CHILD_RUN_STATUSES:
            continue
        await cancel_child_run(
            session,
            row.id,
            error="parent session cancelled",
        )
        if status_publisher is not None:
            await status_publisher.publish_parent_subagent_status(row.id)


async def _get_runner(session_id: str, session: AsyncSession | None = None) -> SessionRunner:
    runner = _SESSION_RUNNERS.get(session_id)
    if runner is not None:
        return runner
    if session is None:
        raise NotFoundError(f"会话不存在: {session_id}")

    task = await task_service.get_task_by_agent_session_id(session, session_id)
    runner = SessionRunner(
        session_id=session_id,
        task_id=task.id,
        model_config={"max_context_tokens": 1},
        project_id=task.project_id,
    )
    graph = await runner._get_graph()
    state = await graph.aget_state({"configurable": {"thread_id": session_id}})
    values = state.values if isinstance(getattr(state, "values", None), dict) else {}
    restored_model_config = values.get("model_config")
    if not _is_valid_model_config(restored_model_config):
        raise NotFoundError(f"会话不存在: {session_id}")
    model_record_id = restored_model_config.get("model_record_id")
    if not isinstance(model_record_id, str) or not model_record_id:
        raise NotFoundError(f"会话不存在: {session_id}")
    runner.model_config = await _resolve_model_config(session, model_record_id)
    restored_agent_key = values.get("agent_key")
    if isinstance(restored_agent_key, str) and restored_agent_key:
        runner.agent_key = restored_agent_key
    _SESSION_RUNNERS[session_id] = runner
    return runner


def _build_model_config(model, provider, api_key: str) -> dict:
    return {
        "model_record_id": model.id,
        "provider_type": provider.provider_type,
        "base_url": provider.url,
        "api_key": api_key,
        "model_id": model.model_id,
        "max_context_tokens": model.context_length,
        "temperature": model.temperature,
        "top_p": model.top_p,
        "top_k": model.top_k,
        "max_tokens": model.max_tokens,
        "frequency_penalty": model.frequency_penalty,
        "presence_penalty": model.presence_penalty,
        "deepseek_reasoning_effort": model.deepseek_reasoning_effort,
        "deepseek_thinking_type": model.deepseek_thinking_type,
    }


async def _resolve_model_config(session: AsyncSession, model_id: str) -> dict:
    model = await model_repo.get_by_id(session, model_id)
    if model is None:
        raise NotFoundError(f"模型不存在：{model_id}")

    provider = await model_provider_repo.get_by_id(session, model.provider_id)
    if provider is None:
        raise NotFoundError(f"模型提供商不存在：{model.provider_id}")

    encryption_service = EncryptionService(settings.encryption_key)
    try:
        api_key = encryption_service.decrypt(provider.api_key_encrypted)
    except Exception as exc:
        raise ValueError("API密钥解密失败") from exc

    return _build_model_config(model, provider, api_key)


async def _set_task_running_state(
    *,
    db_session_factory: Callable[[], AsyncSession],
    task_id: str,
    session_id: str,
    project_id: str,
    is_running: bool,
) -> None:
    status_session = db_session_factory()
    try:
        task = await task_service.update_task(
            status_session,
            task_id=task_id,
            is_running=is_running,
        )
        await status_session.commit()
    finally:
        await status_session.close()

    if project_id:
        await emit(
            "background:event",
            {
                "type": "task_run_status_updated",
                "job_type": "agent_runtime",
                "subject_type": "project",
                "subject_id": project_id,
                "project_id": project_id,
                "task_id": task_id,
                "agent_session_id": session_id,
                "is_running": is_running,
                "payload": {"is_running": is_running},
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "project_revision": time.time_ns(),
            },
            room=background_project_room(project_id),
        )


def _make_status_session_factory(session: AsyncSession) -> Callable[[], AsyncSession]:
    if session.bind is None:
        raise RuntimeError("数据库会话未绑定连接")
    factory = async_sessionmaker(
        session.bind,
        expire_on_commit=False,
    )
    return factory


async def _launch_task(
    *,
    db_session_factory: Callable[[], AsyncSession],
    session_id: str,
    task_id: str,
    project_id: str,
    coro,
) -> None:
    await _set_task_running_state(
        db_session_factory=db_session_factory,
        task_id=task_id,
        session_id=session_id,
        project_id=project_id,
        is_running=True,
    )
    registry = get_agent_run_registry()

    async def _run_and_cleanup() -> None:
        try:
            await coro
        except asyncio.CancelledError:
            logger.bind(session_id=session_id).info("Agent task cancelled")
        except Exception:
            logger.bind(session_id=session_id).opt(exception=True).error("Agent task failed")
        finally:
            current_task = asyncio.current_task()
            removed = False
            if current_task is not None:
                removed = await registry.unregister(session_id, current_task)
            if removed:
                try:
                    if not await registry.is_running(session_id):
                        await _set_task_running_state(
                            db_session_factory=db_session_factory,
                            task_id=task_id,
                            session_id=session_id,
                            project_id=project_id,
                            is_running=False,
                        )
                except Exception:
                    logger.bind(session_id=session_id).opt(exception=True).error(
                        "Agent task running-state cleanup failed"
                    )

    task = asyncio.create_task(_run_and_cleanup())
    try:
        await registry.register(session_id, task)
    except Exception:
        task.cancel()
        await _set_task_running_state(
            db_session_factory=db_session_factory,
            task_id=task_id,
            session_id=session_id,
            project_id=project_id,
            is_running=False,
        )
        raise


async def _replace_registered_parent_task(
    *,
    registry,
    session_id: str,
    current_task: asyncio.Task,
    continuation_task: asyncio.Task,
) -> bool:
    lock = getattr(registry, "_lock", None)
    tasks_by_session = getattr(registry, "_tasks", None)
    if lock is None or not isinstance(tasks_by_session, dict):
        return False

    async with lock:
        session_tasks = tasks_by_session.setdefault(session_id, {})
        if session_tasks.get("__parent__") is not current_task:
            return False
        cancelled_sessions = getattr(registry, "_cancelled_sessions", None)
        discard = getattr(cancelled_sessions, "discard", None)
        if callable(discard):
            discard(session_id)
        session_tasks["__parent__"] = continuation_task
        return True


async def _launch_continuation_task_replacing_current(
    *,
    db_session_factory: Callable[[], AsyncSession],
    session_id: str,
    task_id: str,
    project_id: str,
    registry,
    current_task: asyncio.Task,
    coro,
) -> None:
    async def _run_and_cleanup() -> None:
        try:
            await coro
        except asyncio.CancelledError:
            logger.bind(session_id=session_id).info("Agent continuation task cancelled")
        except Exception:
            logger.bind(session_id=session_id).opt(exception=True).error(
                "Agent continuation task failed"
            )
        finally:
            continuation_task = asyncio.current_task()
            removed = False
            if continuation_task is not None:
                removed = await registry.unregister(session_id, continuation_task)
            if removed:
                try:
                    if not await registry.is_running(session_id):
                        await _set_task_running_state(
                            db_session_factory=db_session_factory,
                            task_id=task_id,
                            session_id=session_id,
                            project_id=project_id,
                            is_running=False,
                        )
                except Exception:
                    logger.bind(session_id=session_id).opt(exception=True).error(
                        "Agent continuation running-state cleanup failed"
                    )

    task = asyncio.create_task(_run_and_cleanup())
    try:
        replaced = await _replace_registered_parent_task(
            registry=registry,
            session_id=session_id,
            current_task=current_task,
            continuation_task=task,
        )
    except Exception:
        task.cancel()
        raise
    if not replaced:
        task.cancel()
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        raise RuntimeError("failed to replace current agent task")


@router.get("/tools", response_model=list[AgentToolMetadataResponse])
async def list_agent_tools() -> list[AgentToolMetadataResponse]:
    items_by_key: dict[str, AgentToolMetadataResponse] = {}

    for tool in ToolRegistry.get_tools(state={"session_id": "", "project_id": ""}):
        display = TOOL_DISPLAY_METADATA.get(tool.name)
        if display is None:
            continue
        items_by_key[tool.name] = AgentToolMetadataResponse(
            key=tool.name,
            name=display["name"],
            description=display["description"],
            is_readonly=tool.access_level == "readonly",
        )

    return sorted(items_by_key.values(), key=lambda item: TOOL_DISPLAY_ORDER.get(item.key, 999))


@router.post("/sessions", response_model=AgentSessionCreateResponse)
async def create_agent_session(
    request: AgentSessionCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentSessionCreateResponse:
    try:
        definition = await load_agent_definition(session, request.agent_key)
        if not definition.enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"主智能体 '{request.agent_key}' 已被禁用",
            )
        if definition.kind != "primary":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"智能体 '{request.agent_key}' 不是主智能体 (kind != primary)",
            )
        model_config = await _resolve_model_config(session, request.model_id)
        session_id = f"agent_{generate_id()}"
        task = await task_service.create_task(
            session=session,
            project_id=request.project_id,
            title="New session",
            mode="agent",
            agent_session_id=session_id,
        )
        task.title = _build_default_agent_session_title(task.created_at)
        runner = SessionRunner(
            session_id=session_id,
            task_id=task.id,
            model_config=model_config,
            project_id=request.project_id,
            agent_key=request.agent_key,
        )
        await runner.materialize_state(
            _build_seed_state(
                session_id=session_id,
                task_id=task.id,
                project_id=request.project_id,
                model_config=model_config,
                agent_key=request.agent_key,
            )
        )
        _SESSION_RUNNERS[session_id] = runner
        await session.commit()
        return AgentSessionCreateResponse(
            session_id=session_id,
            project_id=request.project_id,
            status="created",
            task_id=task.id,
            task_title=task.title,
            task_created_at=task.created_at.isoformat(),
            task_updated_at=task.updated_at.isoformat(),
            agent_key=request.agent_key,
        )
    except HTTPException:
        raise
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    except Exception as exc:
        logger.opt(exception=True).error("创建 Agent 会话失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建会话失败: {exc}",
        )


@router.post("/sessions/{session_id}/message", response_model=AgentSendMessageResponse)
async def send_agent_message(
    session_id: str,
    body: AgentSendMessageRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentSendMessageResponse:
    runner = await _get_runner(session_id, session)
    registry = get_agent_run_registry()
    task = await task_service.get_task(session, runner.task_id)
    status_session_factory = _make_status_session_factory(session)
    if _is_pending_agent_session_title(task.title):
        await enqueue_session_title_job(session, task, body.message)
        await background_service.commit_and_notify(session)
    if await registry.is_running(session_id):
        pending_message = await runner.queue_pending_user_message(body.message)
        return AgentSendMessageResponse(
            success=True,
            session_id=session_id,
            message="Agent 消息已排队",
            queued=True,
            model_updated=False,
            pending_message=AgentPendingMessageResponse(**pending_message),
        )
    can_continue = await runner.can_continue()
    model_updated = False
    if body.model_id and not can_continue:
        try:
            runner.update_model_config(await _resolve_model_config(session, body.model_id))
            model_updated = True
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc
    if can_continue:
        coro = runner.continue_with_user_message(body.message)
    else:
        coro = runner.run(user_request=body.message)
    await _launch_task(
        db_session_factory=status_session_factory,
        session_id=session_id,
        task_id=runner.task_id,
        project_id=runner.project_id,
        coro=coro,
    )
    return AgentSendMessageResponse(
        success=True,
        session_id=session_id,
        message="Agent 任务已启动",
        queued=False,
        model_updated=model_updated,
        pending_message=None,
    )


@router.post(
    "/sessions/{session_id}/pending-message/cancel",
    response_model=AgentCancelPendingMessageResponse,
)
async def cancel_agent_pending_message(
    session_id: str,
    body: AgentCancelPendingMessageRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentCancelPendingMessageResponse:
    runner = await _get_runner(session_id, session)
    restored = await runner.cancel_pending_user_message(body.message_id)
    if restored is None:
        raise NotFoundError(f"pending message not found: {body.message_id}")
    return AgentCancelPendingMessageResponse(
        success=True,
        session_id=session_id,
        message_id=restored["message_id"],
        restored_message_content=restored["content"],
    )


@router.post(
    "/sessions/{session_id}/compaction",
    response_model=AgentCompactionResponse,
)
async def compact_agent_session(
    session_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentCompactionResponse:
    runner = await _get_runner(session_id, session)
    registry = get_agent_run_registry()
    if await registry.is_running(session_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "session_compacting",
                "message": "会话运行中，不能手动压缩",
            },
        )

    current_task = asyncio.current_task()
    if current_task is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="无法注册手动压缩任务",
        )
    current_task = cast(asyncio.Task[None], current_task)
    registered = False
    running_state_started = False
    continuation_started = False
    removed = False
    pending_message: tuple[str, str] | None = None
    compaction_error: CompactionError | None = None
    result: dict[str, int | str] | None = None
    status_session_factory = _make_status_session_factory(session)

    try:
        registered = await registry.try_register_parent(session_id, current_task)
        if not registered:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "session_compacting",
                    "message": "会话运行中，不能手动压缩",
                },
            )
        await _set_task_running_state(
            db_session_factory=status_session_factory,
            task_id=runner.task_id,
            session_id=session_id,
            project_id=runner.project_id,
            is_running=True,
        )
        running_state_started = True
        try:
            result = await runner.compact()
            pending_message = (
                await runner.consume_next_pending_user_message_for_continuation()
            )
            if pending_message is not None:
                message_id, content = pending_message
                await _launch_continuation_task_replacing_current(
                    db_session_factory=status_session_factory,
                    session_id=session_id,
                    task_id=runner.task_id,
                    project_id=runner.project_id,
                    registry=registry,
                    current_task=current_task,
                    coro=runner.run(
                        user_request=content,
                        user_message_id=message_id,
                    ),
                )
                continuation_started = True
        except CompactionError as exc:
            compaction_error = exc
    finally:
        if registered:
            removed = await registry.unregister(session_id, current_task)
        if running_state_started and not continuation_started:
            try:
                if removed and not await registry.is_running(session_id):
                    await _set_task_running_state(
                        db_session_factory=status_session_factory,
                        task_id=runner.task_id,
                        session_id=session_id,
                        project_id=runner.project_id,
                        is_running=False,
                    )
            except Exception:
                logger.bind(session_id=session_id).opt(exception=True).error(
                    "Agent compaction running-state cleanup failed"
                )

    if compaction_error is not None:
        error_status = (
            status.HTTP_409_CONFLICT
            if compaction_error.code
            in {
                "no_compactable_window",
                "compaction_empty_summary",
                "compaction_conflict",
            }
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(
            status_code=error_status,
            detail={
                "code": compaction_error.code,
                "message": compaction_error.message,
            },
        ) from compaction_error

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="手动压缩未返回结果",
        )

    return AgentCompactionResponse(
        success=True,
        session_id=session_id,
        compaction_id=str(result["compaction_id"]),
        start_seq=int(result["start_seq"]),
        end_seq=int(result["end_seq"]),
        source_input_tokens=int(result.get("source_input_tokens", 0)),
        summary_tokens=int(result.get("summary_tokens", 0)),
    )


@router.post("/sessions/{session_id}/question-answer")
async def submit_agent_question_answer(
    session_id: str,
    body: AgentQuestionAnswerRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    runner = await _get_runner(session_id, session)
    status_session_factory = _make_status_session_factory(session)
    payload = {
        "action_type": "clarification",
        "action_id": body.action_id,
        "answer": body.answer,
    }
    await _launch_task(
        db_session_factory=status_session_factory,
        session_id=session_id,
        task_id=runner.task_id,
        project_id=runner.project_id,
        coro=runner.resume(payload),
    )
    return {"success": True, "session_id": session_id, "message": "已提交澄清回答"}


@router.post("/sessions/{session_id}/tool-approval")
async def submit_agent_tool_approval(
    session_id: str,
    body: AgentToolApprovalRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    runner = await _get_runner(session_id, session)
    status_session_factory = _make_status_session_factory(session)
    payload = {
        "action_type": "tool_approval",
        "approval_id": body.approval_id,
        "approved": body.approved,
    }
    child_run = await get_child_run_by_pending_approval(
        session,
        parent_session_id=session_id,
        approval_id=body.approval_id,
    )
    if child_run is not None:
        subagent_runner = SubagentRunner(
            session_factory=status_session_factory,
            model_config=runner.model_config,
            project_id=runner.project_id,
        )
        await _set_task_running_state(
            db_session_factory=status_session_factory,
            session_id=session_id,
            task_id=runner.task_id,
            project_id=runner.project_id,
            is_running=True,
        )
        await ensure_child_processing(
            parent_session_id=session_id,
            child_run_id=child_run.id,
            runner=subagent_runner,
            resume_payload=payload,
        )
        return {"success": True, "session_id": session_id, "message": "已提交工具审批"}

    await _launch_task(
        db_session_factory=status_session_factory,
        session_id=session_id,
        task_id=runner.task_id,
        project_id=runner.project_id,
        coro=runner.resume(payload),
    )
    return {"success": True, "session_id": session_id, "message": "已提交工具审批"}


@router.get("/sessions/{session_id}", response_model=AgentSessionStateResponse)
async def get_agent_session_state(
    session_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentSessionStateResponse:
    runner = await _get_runner(session_id, session)
    graph = await runner._get_graph()
    state = await graph.aget_state({"configurable": {"thread_id": session_id}})
    is_running = await get_agent_run_registry().is_running(session_id)
    if not state.values and not is_running:
        raise NotFoundError(f"会话不存在: {session_id}")
    return AgentSessionStateResponse(
        session_id=session_id,
        state=dict(state.values or {}),
        is_running=is_running,
    )


@router.get(
    "/sessions/{parent_session_id}/subagents",
    response_model=list[ActiveSubagentStateResponse],
)
async def list_subagent_sessions(
    parent_session_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[ActiveSubagentStateResponse]:
    rows = await list_active_child_runs(
        session,
        parent_session_id=parent_session_id,
    )
    items: list[ActiveSubagentStateResponse] = []
    for row in rows:
        items.append(
            _build_subagent_state_response(
                child_run=row,
                queued_messages=await count_pending_child_run_requests(session, row.id),
            )
        )
    return items


@router.get("/subagents/{child_run_id}", response_model=SubagentSessionResponse)
async def get_subagent_session(
    child_run_id: str,
    session: AsyncSession = Depends(get_session),
) -> SubagentSessionResponse:
    row = await session.get(AgentChildRun, child_run_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"子运行不存在: {child_run_id}",
        )

    messages = await load_task_messages_for_agent_session(session, row.child_thread_id)
    metadata = dict(row.metadata_json or {})
    token_usage = metadata.pop("token_usage", {})
    usage = token_usage if isinstance(token_usage, dict) else {}
    return SubagentSessionResponse(
        child_run_id=row.id,
        parent_session_id=row.parent_session_id,
        parent_task_id=row.parent_task_id,
        parent_thread_id=row.parent_thread_id,
        child_thread_id=row.child_thread_id,
        agent_key=row.agent_key,
        agent_number=get_child_run_agent_number(row.metadata_json),
        dispatch_id=row.dispatch_id,
        tool_call_id=row.tool_call_id,
        status=row.status,
        queued_messages=await count_pending_child_run_requests(session, row.id),
        is_active=row.is_active,
        is_running=await get_agent_run_registry().is_child_running(
            row.parent_session_id,
            row.id,
        ),
        request=dict(row.request_json or {}),
        result=dict(row.result_json) if row.result_json is not None else None,
        pending_approval=(
            dict(row.pending_approval_json)
            if row.pending_approval_json is not None
            else None
        ),
        error=row.error,
        metadata=metadata,
        token_input=int(usage.get("token_input", 0) or 0),
        token_output=int(usage.get("token_output", 0) or 0),
        token_cache=int(usage.get("token_cache", 0) or 0),
        context_input_tokens=int(usage.get("context_input_tokens", 0) or 0),
        context_length=int(usage.get("context_length", 0) or 0),
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        messages=messages,
    )


@router.post("/sessions/{session_id}/rollback", response_model=AgentRollbackResponse)
async def rollback_agent_session(
    session_id: str,
    request: AgentRollbackRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentRollbackResponse:
    registry = get_agent_run_registry()
    is_running = getattr(registry, "is_running", None)
    if callable(is_running) and await is_running(session_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="会话运行中，不能回滚",
        )

    runner = _SESSION_RUNNERS.get(session_id)
    if runner is not None:
        runner.cancel()
        cancel = getattr(registry, "cancel", None)
        if callable(cancel):
            await cancel(session_id)

    result = await rollback_revision_for_session(
        session,
        agent_session_id=session_id,
        revision_id=request.revision_id,
    )
    await session.commit()

    if result.restored_checkpoint_id:
        try:
            await delete_checkpoints_after_for_thread(
                session_id, result.restored_checkpoint_id
            )
        except Exception:
            logger.bind(session_id=session_id).opt(exception=True).error(
                "Agent graph checkpoint rollback failed after revision rollback"
            )
            raise
    if result.affected_child_run_ids:
        status_publisher = SubagentRunner(
            session_factory=_make_status_session_factory(session),
            model_config=runner.model_config if runner is not None else {"max_context_tokens": 1},
            project_id=runner.project_id if runner is not None else "",
        )
        for child_run_id in result.affected_child_run_ids:
            await status_publisher.publish_parent_subagent_status(child_run_id)
    emitted_global_chapter_refresh = False
    for chapter_id in result.affected_chapters:
        payload = {
            "session_id": session_id,
            "project_id": result.rollback_revision.project_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        if await session.get(Chapter, chapter_id) is not None:
            payload["chapter_id"] = chapter_id
        elif emitted_global_chapter_refresh:
            continue
        else:
            emitted_global_chapter_refresh = True
        await emit(
            "agent:chapter_refresh",
            payload,
            room=agent_session_room(session_id),
        )
    for child_thread_id, checkpoint_id in result.child_checkpoint_boundaries:
        try:
            if checkpoint_id:
                await delete_checkpoints_after_for_thread(child_thread_id, checkpoint_id)
            else:
                await delete_checkpoints_for_thread(child_thread_id)
        except Exception:
            logger.bind(
                session_id=session_id,
                child_thread_id=child_thread_id,
            ).opt(exception=True).error(
                "Agent subagent checkpoint rollback failed after revision rollback"
            )
            raise

    return AgentRollbackResponse(
        success=True,
        session_id=session_id,
        revision_id=result.rollback_revision.id,
        affected_chapters=result.affected_chapters,
        affected_notes=result.affected_notes,
        affected_note_categories=result.affected_note_categories,
        affected_world_entries=result.affected_world_entries,
        restored_message_content=result.restored_message_content,
    )


@router.post("/sessions/{session_id}/fork", response_model=AgentForkResponse)
async def fork_agent_session(
    session_id: str,
    request: AgentForkRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentForkResponse:
    if await get_agent_run_registry().is_running(session_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="会话运行中，不能分叉",
        )

    fork_session_id: str | None = None
    try:
        model_config = await _resolve_model_config(session, request.model_id)
        result = await fork_agent_session_at_revision(
            session,
            source_session_id=session_id,
            source_revision_id=request.source_revision_id,
            model_config=model_config,
        )
        runner = SessionRunner(
            session_id=result.session_id,
            task_id=result.task.id,
            model_config=model_config,
            project_id=result.task.project_id,
        )
        fork_session_id = result.session_id
        _SESSION_RUNNERS[result.session_id] = runner
        await runner.materialize_state(result.state_values)
        await session.commit()
        return AgentForkResponse(
            session_id=result.session_id,
            task_id=result.task.id,
            task_title=result.task.title,
            task_created_at=result.task.created_at.isoformat(),
            task_updated_at=result.task.updated_at.isoformat(),
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        if fork_session_id:
            _SESSION_RUNNERS.pop(fork_session_id, None)
        logger.bind(session_id=session_id).opt(exception=True).error("Agent 会话分叉失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分叉失败: {exc}",
        )


@router.post("/sessions/{session_id}/cancel", response_model=AgentCancelResponse)
async def cancel_agent_session(
    session_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentCancelResponse:
    runner = await _get_runner(session_id, session)
    status_session_factory = _make_status_session_factory(session)
    status_publisher = SubagentRunner(
        session_factory=status_session_factory,
        model_config=runner.model_config,
        project_id=runner.project_id,
    )
    runner.cancel()
    await _cancel_subagent_session_tree(
        session,
        root_session_id=session_id,
        status_publisher=status_publisher,
    )
    return AgentCancelResponse(
        success=True,
        session_id=session_id,
        message="会话已取消",
    )
