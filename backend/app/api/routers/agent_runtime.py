# -*- coding: utf-8 -*-
"""Agent API Router - new agent_runtime-backed workflow."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from typing import TypeGuard, cast

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent_runtime.agents.definitions import load_agent_definition
from app.agent_runtime.attachments import (
    get_agent_attachment_url,
    load_session_attachments,
    save_agent_image_attachment,
    serialize_agent_attachment,
)
from app.agent_runtime.context.compaction.service import CompactionError
from app.agent_runtime.persistence.child_runs import get_child_run_by_pending_approval
from app.agent_runtime.persistence.child_runs import (
    TERMINAL_CHILD_RUN_STATUSES,
    count_pending_child_run_requests,
    cancel_child_run,
    get_child_run_for_parent,
    list_active_child_runs,
    list_child_runs_for_parent,
)
from app.agent_runtime.persistence.child_runs import get_child_run_agent_number
from app.agent_runtime.persistence.task_projection import (
    load_task_messages_for_agent_session,
)
from app.agent_runtime.persistence.model import AgentChildRun
from app.agent_runtime.revisions import finalize_revision_status, rollback_revision_for_session
from app.agent_runtime.fork import fork_agent_session_at_revision
from app.agent_runtime.model_config import without_api_key
from app.agent_runtime.runner.checkpointer import (
    delete_checkpoints_after_for_thread,
    delete_checkpoints_for_thread,
    get_checkpointer,
)
from app.agent_runtime.runner.session_runner import SessionRunner
from app.agent_runtime.runner.subagent_runner import SubagentRunner
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.agent_runtime.streaming.replay_buffer import get_agent_event_replay_buffer
from app.agent_runtime.tools import ToolRegistry
from app.agent_runtime.tools.impls.orchestration.common import ensure_child_processing
from app.api.schemas.agent import (
    AgentCancelPendingMessageRequest,
    AgentCancelPendingMessageResponse,
    AgentCancelResponse,
    AgentAttachmentResponse,
    AgentCompactionResponse,
    AgentForkRequest,
    AgentForkResponse,
    AgentPendingMessageResponse,
    AgentQuestionAnswerRequest,
    AgentInterruptResumeRequest,
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
from app.storage.repos import revision_repo
from app.storage.services import task_service

router = APIRouter(tags=["Agent"])

LEGACY_DEFAULT_AGENT_SESSION_TITLE = "Agent Session"
DEFAULT_AGENT_SESSION_TITLE_PREFIX = "New session - "
DEFAULT_AGENT_SESSION_TITLE_PATTERN = re.compile(
    r"^New session - \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
)

TOOL_DISPLAY_ORDER = {
    "ask_user": 0,
    "write_plan": 1,
    "dispatch_subagent": 2,
    "notify_subagent": 3,
    "recycle_subagent": 4,
    "list_volumes": 5,
    "list_chapters": 6,
    "read_chapter": 7,
    "search_chapters": 8,
    "update_index": 9,
    "read_chapter_summaries": 10,
    "read_range_summaries": 11,
    "write_chapter": 12,
    "edit_chapter": 13,
    "delete_chapter": 14,
    "create_volume": 15,
    "edit_volume": 16,
    "delete_volume": 17,
    "move_chapter_to_volume": 18,
    "list_notes": 19,
    "read_note": 20,
    "write_note": 21,
    "edit_note": 22,
    "delete_note": 23,
    "move_note": 24,
    "create_note_category": 25,
    "edit_note_category": 26,
    "delete_note_category": 27,
    "list_characters": 28,
    "read_character": 29,
    "create_character": 30,
    "edit_character": 31,
    "delete_character": 32,
    "list_world_entries": 33,
    "read_world_entry": 34,
    "create_world_entry": 35,
    "edit_world_entry": 36,
    "delete_world_entry": 37,
    "activate_skill": 38,
    "reference_skill": 39,
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
    agent_key: str = "build",
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
        "user_attachments": [],
        "current_revision_id": current_revision_id,
        "messages": [],
    }


def _is_valid_model_config(model_config: object) -> TypeGuard[dict[str, object]]:
    if not isinstance(model_config, dict):
        return False
    max_context_tokens = model_config.get("max_context_tokens")
    return isinstance(max_context_tokens, int) and max_context_tokens >= 0


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


async def _get_runner(
    session_id: str,
    session: AsyncSession | None = None,
    model_config: dict | None = None,
) -> SessionRunner:
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
    if model_config is not None:
        runner.model_config = model_config
    elif isinstance(model_record_id, str) and model_record_id:
        restored_reasoning_effort = restored_model_config.get("reasoning_effort")
        runner.model_config = await _resolve_model_config(
            session,
            model_record_id,
            restored_reasoning_effort
            if isinstance(restored_reasoning_effort, str)
            else None,
        )
    else:
        runner.model_config = await _resolve_legacy_model_config(
            session,
            restored_model_config,
        )
        await graph.aupdate_state(
            {"configurable": {"thread_id": session_id}},
            {"model_config": without_api_key(runner.model_config)},
            as_node="primary",
        )
    restored_agent_key = values.get("agent_key")
    if isinstance(restored_agent_key, str) and restored_agent_key:
        try:
            await _validate_primary_agent(session, restored_agent_key)
        except HTTPException:
            await graph.aupdate_state(
                {"configurable": {"thread_id": session_id}},
                {"agent_key": "build"},
                as_node="primary",
            )
        else:
            runner.agent_key = restored_agent_key
    _SESSION_RUNNERS[session_id] = runner
    return runner


async def _is_agent_session_cancelled(
    session: AsyncSession,
    session_id: str,
) -> bool:
    """Whether the current revision was terminally cancelled.

    LangGraph keeps an interrupt checkpoint after a cancellation so that a
    normal paused session can be restored.  A cancelled revision, however,
    must never be resumed from that checkpoint.
    """

    try:
        task = await task_service.get_task_by_agent_session_id(session, session_id)
    except NotFoundError:
        return False
    if not task.current_revision_id:
        return False
    revision = await revision_repo.get_by_id(session, task.current_revision_id)
    return revision is not None and revision.status == "cancelled"


async def _ensure_agent_session_resumable(
    session: AsyncSession,
    session_id: str,
) -> None:
    if await _is_agent_session_cancelled(session, session_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "session_cancelled",
                "message": "会话已取消，无法恢复待处理的审批或问答",
            },
        )


async def _claim_agent_session_resume(
    session: AsyncSession,
    session_id: str,
    *,
    allow_active: bool = False,
) -> tuple[str | None, bool]:
    """Reserve the interrupted revision and report whether this request claimed it.

    This conditional transition serializes a competing cancel or duplicate
    resume across application workers before a runner task is launched.
    """

    task = await task_service.get_task_by_agent_session_id(session, session_id)
    revision_id = task.current_revision_id
    if not revision_id:
        return None, False
    if await revision_repo.claim_interrupted_revision(session, revision_id):
        await session.commit()
        return revision_id, True

    revision = await revision_repo.get_by_id(session, revision_id)
    if revision is not None and revision.status == "cancelled":
        await _ensure_agent_session_resumable(session, session_id)
    if allow_active and revision is not None and revision.status == "active":
        return revision_id, False
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "session_not_resumable",
            "message": "会话当前不在可恢复的中断状态",
        },
    )


@asynccontextmanager
async def _agent_session_lifecycle_lock(registry, session_id: str):
    """Serialize cancellation with starting or queuing a parent run."""

    lock_factory = getattr(registry, "session_lock", None)
    if callable(lock_factory):
        async with lock_factory(session_id):
            yield
    else:
        # Keep lightweight router tests with fake registries backwards-compatible.
        yield


async def _release_agent_session_resume_claim(
    session: AsyncSession,
    revision_id: str | None,
) -> None:
    """Make a claimed checkpoint resumable again when its launch fails."""

    if not revision_id:
        return
    if await revision_repo.release_active_revision_claim(session, revision_id):
        await session.commit()


async def _build_model_config(
    model, provider, api_key: str, reasoning_effort: str | None = None
) -> dict:
    model_config = {
        "model_record_id": model.id,
        "provider_type": provider.provider_type,
        "base_url": provider.url,
        "api_key": api_key,
        "model_id": model.model_id,
        "max_context_tokens": model.context_length,
        "input_price": getattr(model, "input_price", 0.0),
        "output_price": getattr(model, "output_price", 0.0),
        "cache_read_price": getattr(model, "cache_read_price", 0.0),
        "cache_write_price": getattr(model, "cache_write_price", 0.0),
        "temperature": model.temperature,
        "top_p": model.top_p,
        "top_k": model.top_k,
        "min_p": model.min_p,
        "top_a": model.top_a,
        "max_tokens": model.max_tokens,
        "frequency_penalty": model.frequency_penalty,
        "presence_penalty": model.presence_penalty,
        "repetition_penalty": model.repetition_penalty,
    }
    if reasoning_effort and reasoning_effort != "off":
        model_config["reasoning_effort"] = reasoning_effort
    return model_config


async def _validate_primary_agent(session: AsyncSession, agent_key: str) -> None:
    try:
        definition = await load_agent_definition(session, agent_key)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"主智能体不存在: {agent_key}",
        ) from exc
    if not definition.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"主智能体 '{agent_key}' 已被禁用",
        )
    if definition.kind != "primary":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"智能体 '{agent_key}' 不是主智能体 (kind != primary)",
        )


async def _resolve_model_config(
    session: AsyncSession, model_id: str, reasoning_effort: str | None = None
) -> dict:
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

    return await _build_model_config(model, provider, api_key, reasoning_effort)


async def _resolve_legacy_model_config(
    session: AsyncSession,
    legacy_model_config: dict[str, object],
) -> dict:
    model_id = legacy_model_config.get("model_id")
    provider_type = legacy_model_config.get("provider_type")
    base_url = legacy_model_config.get("base_url")
    if (
        not isinstance(model_id, str)
        or not model_id
        or not isinstance(provider_type, str)
        or not provider_type
        or not isinstance(base_url, str)
        or not base_url
    ):
        raise NotFoundError("会话模型配置无法恢复")

    model = await model_repo.get_by_legacy_agent_config(
        session,
        model_id=model_id,
        provider_type=provider_type,
        base_url=base_url,
    )
    if model is None:
        raise NotFoundError("会话模型配置无法恢复")
    return await _resolve_model_config(session, model.id)


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

    await emit(
        "agent:settings_lock_changed",
        {
            "session_id": session_id,
            "is_running": is_running,
        },
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
    clear_cancelled: bool = True,
    lifecycle_lock_held: bool = False,
) -> None:
    registry = get_agent_run_registry()

    start_gate = asyncio.Event()

    async def _run_and_cleanup() -> None:
        started = False
        try:
            await start_gate.wait()
            started = True
            await coro
        except asyncio.CancelledError:
            logger.bind(session_id=session_id).info("Agent task cancelled")
        except Exception:
            logger.bind(session_id=session_id).opt(exception=True).error("Agent task failed")
        finally:
            if not started:
                close = getattr(coro, "close", None)
                if callable(close):
                    with suppress(Exception):
                        close()
            async with _agent_session_lifecycle_lock(registry, session_id):
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

    async def _register_and_start() -> None:
        if clear_cancelled:
            await registry.register(session_id, task)
        else:
            await registry.register(session_id, task, clear_cancelled=False)
        # Register before the task can enter SessionRunner.resume. A concurrent
        # cancellation then either remains visible to the runner or cancels the
        # registered task, instead of being erased by a late registration.
        await _set_task_running_state(
            db_session_factory=db_session_factory,
            task_id=task_id,
            session_id=session_id,
            project_id=project_id,
            is_running=True,
        )
        start_gate.set()

    try:
        if lifecycle_lock_held:
            await _register_and_start()
        else:
            async with _agent_session_lifecycle_lock(registry, session_id):
                await _register_and_start()
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
            async with _agent_session_lifecycle_lock(registry, session_id):
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
        if tool.name not in TOOL_DISPLAY_ORDER:
            continue
        items_by_key[tool.name] = AgentToolMetadataResponse(
            key=tool.name,
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
        model_config = await _resolve_model_config(
            session, request.model_id, request.reasoning_effort
        )
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


@router.post(
    "/sessions/{session_id}/attachments",
    response_model=AgentAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_agent_attachment(
    session_id: str,
    image: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> AgentAttachmentResponse:
    """上传一张仅供指定 Agent 会话使用的图片附件。"""
    task = await task_service.get_task_by_agent_session_id(session, session_id)
    try:
        attachment = await save_agent_image_attachment(
            session,
            session_id=session_id,
            task_id=task.id,
            project_id=task.project_id,
            image_file=image,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AgentAttachmentResponse(
        id=attachment.id,
        session_id=attachment.session_id,
        storage_name=attachment.storage_name,
        file_name=attachment.file_name,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        width=attachment.width,
        height=attachment.height,
        url=get_agent_attachment_url(attachment.storage_name),
    )


@router.post("/sessions/{session_id}/message", response_model=AgentSendMessageResponse)
async def send_agent_message(
    session_id: str,
    body: AgentSendMessageRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentSendMessageResponse:
    if not body.message.strip() and not body.attachments:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息或图片不能为空")
    requested_model_config: dict | None = None
    if body.model_id and session_id not in _SESSION_RUNNERS:
        try:
            requested_model_config = await _resolve_model_config(
                session, body.model_id, body.reasoning_effort
            )
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

    runner = await _get_runner(session_id, session, requested_model_config)
    try:
        attachments = await load_session_attachments(
            session,
            session_id=session_id,
            attachment_ids=body.attachments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    attachment_metadata = [serialize_agent_attachment(attachment) for attachment in attachments]
    registry = get_agent_run_registry()
    task = await task_service.get_task(session, runner.task_id)
    status_session_factory = _make_status_session_factory(session)
    if _is_pending_agent_session_title(task.title):
        await enqueue_session_title_job(session, task, body.message)
        await background_service.commit_and_notify(session)
    async with _agent_session_lifecycle_lock(registry, session_id):
        if await registry.is_running(session_id) and not await registry.is_cancelled(session_id):
            queue_kwargs = {"attachments": attachment_metadata} if attachment_metadata else {}
            pending_message = await runner.queue_pending_user_message(body.message, **queue_kwargs)
            return AgentSendMessageResponse(
                success=True,
                session_id=session_id,
                message="Agent 消息已排队",
                queued=True,
                model_updated=False,
                pending_message=AgentPendingMessageResponse(**pending_message),
            )
    model_updated = False
    if body.model_id:
        try:
            if requested_model_config is None:
                requested_model_config = await _resolve_model_config(
                    session, body.model_id, body.reasoning_effort
                )
            runner.update_model_config(
                requested_model_config
            )
            model_updated = True
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc
    elif body.reasoning_effort is not None:
        model_record_id = runner.model_config.get("model_record_id")
        if isinstance(model_record_id, str) and model_record_id:
            runner.update_model_config(
                await _resolve_model_config(
                    session, model_record_id, body.reasoning_effort
                )
            )
    if body.agent_key:
        await _validate_primary_agent(session, body.agent_key)
        runner.agent_key = body.agent_key
    run_kwargs = {"attachments": attachment_metadata} if attachment_metadata else {}
    coro = runner.run(user_request=body.message, **run_kwargs)
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
    return await _run_agent_session_compaction(
        session_id=session_id,
        session=session,
        runner=runner,
        registry=registry,
    )


async def _run_agent_session_compaction(
    *,
    session_id: str,
    session: AsyncSession,
    runner: SessionRunner,
    registry,
) -> AgentCompactionResponse:
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
        # Only serialize the lifecycle transition. The compaction task remains
        # registered in the run registry after this block, so other LLM calls
        # still see the session as running while cancellation can acquire the
        # lifecycle lock and cancel this task.
        async with _agent_session_lifecycle_lock(registry, session_id):
            await _ensure_agent_session_resumable(session, session_id)
            if await registry.is_running(session_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "session_compacting",
                        "message": "会话运行中，不能手动压缩",
                    },
                )
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
            async with _agent_session_lifecycle_lock(registry, session_id):
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
        async with _agent_session_lifecycle_lock(registry, session_id):
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
    await _ensure_agent_session_resumable(session, session_id)
    runner = await _get_runner(session_id, session)
    status_session_factory = _make_status_session_factory(session)
    payload = {
        "action_type": "clarification",
        "action_id": body.action_id,
        "answer": [item.model_dump(mode="json") for item in body.answer],
    }
    if body.skipped:
        payload["skipped"] = True
    registry = get_agent_run_registry()
    async with _agent_session_lifecycle_lock(registry, session_id):
        revision_id, claimed_revision = await _claim_agent_session_resume(session, session_id)
        try:
            await _launch_task(
                db_session_factory=status_session_factory,
                session_id=session_id,
                task_id=runner.task_id,
                project_id=runner.project_id,
                coro=runner.resume(payload),
                clear_cancelled=False,
                lifecycle_lock_held=True,
            )
        except Exception:
            if claimed_revision:
                await _release_agent_session_resume_claim(session, revision_id)
            raise
    return {"success": True, "session_id": session_id, "message": "已提交澄清回答"}


@router.post("/sessions/{session_id}/interrupt-resume")
async def submit_agent_interrupt_resume(
    session_id: str,
    body: AgentInterruptResumeRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _ensure_agent_session_resumable(session, session_id)
    runner = await _get_runner(session_id, session)
    status_session_factory = _make_status_session_factory(session)
    responses = [item.model_dump(mode="json", exclude_none=True) for item in body.responses]
    registry = get_agent_run_registry()
    async with _agent_session_lifecycle_lock(registry, session_id):
        revision_id, claimed_revision = await _claim_agent_session_resume(session, session_id)
        try:
            await _launch_task(
                db_session_factory=status_session_factory,
                session_id=session_id,
                task_id=runner.task_id,
                project_id=runner.project_id,
                coro=runner.resume_interrupt_batch(body.batch_id, responses),
                clear_cancelled=False,
                lifecycle_lock_held=True,
            )
        except Exception:
            if claimed_revision:
                await _release_agent_session_resume_claim(session, revision_id)
            raise
    return {"success": True, "session_id": session_id, "message": "已提交并行中断响应"}


@router.post("/sessions/{session_id}/tool-approval")
async def submit_agent_tool_approval(
    session_id: str,
    body: AgentToolApprovalRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _ensure_agent_session_resumable(session, session_id)
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
    registry = get_agent_run_registry()
    if child_run is not None:
        async with _agent_session_lifecycle_lock(registry, session_id):
            # The initial check above can race a cancellation. Recheck while holding
            # the same lifecycle lock before marking the parent task as running.
            await _ensure_agent_session_resumable(session, session_id)
            revision_id, claimed_revision = await _claim_agent_session_resume(
                session, session_id, allow_active=True
            )
            started = False
            try:
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
                started = await ensure_child_processing(
                    parent_session_id=session_id,
                    child_run_id=child_run.id,
                    runner=subagent_runner,
                    resume_payload=payload,
                    clear_cancelled=False,
                )
                if not started and await registry.is_cancelled(session_id):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "code": "session_cancelled",
                            "message": "会话已取消，无法恢复待处理的审批或问答",
                        },
                    )
            except Exception:
                if not started:
                    try:
                        await _set_task_running_state(
                            db_session_factory=status_session_factory,
                            session_id=session_id,
                            task_id=runner.task_id,
                            project_id=runner.project_id,
                            is_running=False,
                        )
                    except Exception:
                        logger.bind(session_id=session_id).opt(exception=True).error(
                            "Child agent launch running-state rollback failed"
                        )
                if claimed_revision:
                    await _release_agent_session_resume_claim(session, revision_id)
                raise
        return {"success": True, "session_id": session_id, "message": "已提交工具审批"}

    async with _agent_session_lifecycle_lock(registry, session_id):
        revision_id, claimed_revision = await _claim_agent_session_resume(session, session_id)
        try:
            await _launch_task(
                db_session_factory=status_session_factory,
                session_id=session_id,
                task_id=runner.task_id,
                project_id=runner.project_id,
                coro=runner.resume(payload),
                clear_cancelled=False,
                lifecycle_lock_held=True,
            )
        except Exception:
            if claimed_revision:
                await _release_agent_session_resume_claim(session, revision_id)
            raise
    return {"success": True, "session_id": session_id, "message": "已提交工具审批"}


@router.get("/sessions/{session_id}", response_model=AgentSessionStateResponse)
async def get_agent_session_state(
    session_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentSessionStateResponse:
    checkpointer = await get_checkpointer()
    checkpoint = await checkpointer.aget_tuple(
        {"configurable": {"thread_id": session_id}}
    )
    checkpoint_values = checkpoint.checkpoint.get("channel_values") if checkpoint else None
    state_values = dict(checkpoint_values) if isinstance(checkpoint_values, dict) else {}
    is_cancelled = await _is_agent_session_cancelled(session, session_id)
    # A new run can be registered before it commits its new revision.  Keep
    # the live registry state authoritative for running status during that
    # transition, while still suppressing interrupts from the cancelled
    # checkpoint below.
    is_running = await get_agent_run_registry().is_running(session_id)
    if is_cancelled:
        try:
            task = await task_service.get_task_by_agent_session_id(session, session_id)
        except NotFoundError:
            task = None
        if task is not None and not task.is_running:
            is_running = False
    interrupts: list[dict] = []
    if checkpoint is not None and not is_cancelled:
        for pending_write in checkpoint.pending_writes or []:
            if len(pending_write) < 3 or pending_write[1] != "__interrupt__":
                continue
            values = pending_write[2]
            if not isinstance(values, list):
                continue
            for interrupt in values:
                value = getattr(interrupt, "value", None)
                interrupt_id = getattr(interrupt, "id", None)
                if not isinstance(value, dict) or not isinstance(interrupt_id, str):
                    continue
                payload = dict(value)
                payload["interrupt_id"] = interrupt_id
                if payload.get("type") == "tool_approval":
                    payload["approval_id"] = interrupt_id
                    payload["id"] = interrupt_id
                elif payload.get("type") == "ask_user":
                    payload["action_id"] = interrupt_id
                    payload["id"] = interrupt_id
                interrupts.append(payload)
    if not state_values and not is_running and not interrupts:
        raise NotFoundError(f"会话不存在: {session_id}")
    return AgentSessionStateResponse(
        session_id=session_id,
        state=state_values,
        is_running=is_running,
        interrupts=interrupts,
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
        cost=float(usage.get("cost", 0.0) or 0.0),
        context_input_tokens=int(usage.get("context_input_tokens", 0) or 0),
        context_length=int(usage.get("context_length", 0) or 0),
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        messages=messages,
    )


@router.post(
    "/sessions/{parent_session_id}/subagents/{child_run_id}/cancel",
    response_model=AgentCancelResponse,
)
async def cancel_subagent_session(
    parent_session_id: str,
    child_run_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentCancelResponse:
    """取消单个 subagent 会话。

    中断其当前任务（含重试退避）并把 open requests 标记为 cancelled，
    主会话侧的 wait_for_request_resolution 感知后继续主流程。
    """
    row = await get_child_run_for_parent(
        session,
        parent_session_id=parent_session_id,
        child_run_id=child_run_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="subagent session not found",
        )
    if not row.is_active or row.status in TERMINAL_CHILD_RUN_STATUSES:
        return AgentCancelResponse(
            success=True,
            session_id=child_run_id,
            message="子代理会话已结束",
        )

    await cancel_child_run(
        session,
        child_run_id,
        error="user cancelled subagent",
    )
    await get_agent_run_registry().cancel_child(parent_session_id, child_run_id)
    await session.commit()

    status_publisher = SubagentRunner(
        session_factory=_make_status_session_factory(session),
        model_config={},
        project_id="",
    )
    await status_publisher.publish_parent_subagent_status(child_run_id)
    return AgentCancelResponse(
        success=True,
        session_id=child_run_id,
        message="子代理会话已取消",
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

    replay_buffer = get_agent_event_replay_buffer()
    async with replay_buffer.session_lock(session_id):
        replay_buffer.clear_session_unlocked(session_id)

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
        restored_attachments=[
            AgentAttachmentResponse(
                id=attachment["id"],
                session_id=session_id,
                storage_name=attachment["storage_name"],
                file_name=attachment["file_name"],
                mime_type=attachment["mime_type"],
                size_bytes=attachment["size_bytes"],
                width=attachment["width"],
                height=attachment["height"],
                url=attachment["url"],
            )
            for attachment in result.restored_attachments
            if all(
                key in attachment
                for key in (
                    "id",
                    "storage_name",
                    "file_name",
                    "mime_type",
                    "size_bytes",
                    "width",
                    "height",
                    "url",
                )
            )
        ],
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
        model_config = await _resolve_model_config(
            session,
            request.model_id,
            request.reasoning_effort,
        )
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
    registry = get_agent_run_registry()
    status_session_factory = _make_status_session_factory(session)
    status_publisher = SubagentRunner(
        session_factory=status_session_factory,
        model_config=runner.model_config,
        project_id=runner.project_id,
    )
    session_lock_factory = getattr(registry, "session_lock", None)
    session_lock = (
        session_lock_factory(session_id)
        if callable(session_lock_factory)
        else None
    )
    if session_lock is not None:
        await session_lock.acquire()
    parent_task: asyncio.Task[None] | None = None
    try:
        parent_task = await registry.mark_cancelled(session_id)
        task = await task_service.get_task_by_agent_session_id(session, session_id)
        revision = (
            await revision_repo.get_by_id(session, task.current_revision_id)
            if task.current_revision_id
            else None
        )
        if revision is not None and revision.status in {"active", "interrupted"}:
            await finalize_revision_status(session, revision.id, "cancelled")
        await task_service.update_task(session, task.id, is_running=False)
        await session.commit()
    except Exception:
        if session_lock is not None:
            session_lock.release()
        await registry.clear_cancelled(session_id)
        raise

    # Commit the terminal state before signalling the runner. A resume that
    # races with cancellation will now either observe the cancelled revision
    # before it starts, or receive this cancellation signal afterwards.
    try:
        if parent_task is not None:
            try:
                await registry.cancel_task(session_id, parent_task)
            except Exception:
                logger.bind(session_id=session_id).opt(exception=True).error(
                    "Agent parent task cancellation failed after terminal commit"
                )

        try:
            runner.cancel()
        except Exception:
            logger.bind(session_id=session_id).opt(exception=True).error(
                "Agent runner cancellation signal failed after terminal commit"
            )

        try:
            await _cancel_subagent_session_tree(
                session,
                root_session_id=session_id,
                status_publisher=status_publisher,
            )
            await session.commit()
        except Exception:
            with suppress(Exception):
                await session.rollback()
            logger.bind(session_id=session_id).opt(exception=True).error(
                "Agent subagent cancellation cleanup failed after terminal commit"
            )

        # Keep notifications inside the lifecycle lock. Otherwise a new run
        # can publish is_running=True and then be overwritten by this
        # cancellation's stale is_running=False notification. The terminal
        # database state is already committed, so notification failures must
        # not turn a successful cancellation into an error response.
        if task.project_id:
            try:
                await emit(
                    "background:event",
                    {
                        "type": "task_run_status_updated",
                        "job_type": "agent_runtime",
                        "subject_type": "project",
                        "subject_id": task.project_id,
                        "project_id": task.project_id,
                        "task_id": task.id,
                        "agent_session_id": session_id,
                        "is_running": False,
                        "payload": {"is_running": False},
                        "created_at": datetime.now(UTC).isoformat(),
                        "updated_at": task.updated_at.isoformat(),
                        "project_revision": time.time_ns(),
                    },
                    room=background_project_room(task.project_id),
                )
            except Exception:
                logger.bind(session_id=session_id).opt(exception=True).error(
                    "Agent task status notification failed after cancellation"
                )
        try:
            await emit(
                "agent:settings_lock_changed",
                {"session_id": session_id, "is_running": False},
            )
        except Exception:
            logger.bind(session_id=session_id).opt(exception=True).error(
                "Agent settings-lock notification failed after cancellation"
            )
    finally:
        if session_lock is not None:
            session_lock.release()
    return AgentCancelResponse(
        success=True,
        session_id=session_id,
        message="会话已取消",
    )
