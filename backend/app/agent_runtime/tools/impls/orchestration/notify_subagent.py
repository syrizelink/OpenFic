from __future__ import annotations

import json
from textwrap import dedent
from typing import Any

from pydantic import BaseModel, Field

from app.agent_runtime.persistence.child_runs import (
    MAX_ACTIVE_SUBAGENTS,
    ChildRunCapacityError,
    ChildRunReplayConflict,
    TERMINAL_CHILD_RUN_REQUEST_STATUSES,
    enqueue_child_run_request,
)
from app.agent_runtime.persistence.model import AgentRunMessage
from app.agent_runtime.runner.checkpointer import latest_checkpoint_id_for_thread
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.orchestration.common import (
    close_session,
    ensure_child_processing,
    ensure_primary,
    emit_subagent_tool_preview,
    get_configurable,
    make_subagent_runner,
    open_session,
    publish_child_user_message,
    resolve_child_run,
    start_background_request,
    wait_for_request_resolution,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.core.ids import generate_id


class NotifySubagentInput(BaseModel):
    background: bool = Field(
        default=False,
        description="是否在后台继续会话并立即返回；完成后自动回传结果。默认同步等待。",
    )
    dispatch_id: str = Field(
        min_length=1,
        description="subagent 会话ID",
    )
    prompt: str = Field(
        min_length=1,
        description="要 agent 执行的下一步任务描述或消息",
    )

    model_config = {"extra": "forbid"}


@ToolRegistry.register
class NotifySubagentTool(AgentTool):
    name: str = "notify_subagent"
    description: str = dedent("""\
        向一个Subagent会话发送消息以恢复进程
        使用时，必须指定dispatch_id来选定所要恢复的会话

        使用说明：
        - 恢复的Subagent会话将沿用此前完成时的状态（消息历史、工具输出等），不要提供重复的上下文信息
        - 继续会话时，聚焦于当前任务，明确说明下一步的要求
        - background=true 时消息排队后立即返回，完成后自动回传该 request_id 的结果；同一会话内消息仍按顺序执行
        - 继续忙碌的子代理不增加并发占用；恢复空闲子代理受任务树最多10个活跃子代理的限制
        - 同一批工具调用中，每个dispatch_id只接受第一条通知；后续通知须等前一条返回后再发送
        - 一个Subagent会话被关闭后，对应dispatch_id就会失效且无法使用
    """)
    access_level: str = "readonly"
    args_schema: type[BaseModel] = NotifySubagentInput

    async def _wait_for_assistant_content(
        self,
        *,
        configurable: dict[str, Any],
        child_run_id: str,
        request_id: str,
        runner: Any,
        start_processing: bool = True,
    ) -> str:
        if start_processing:
            await ensure_child_processing(
                parent_session_id=self.session_id,
                child_run_id=child_run_id,
                runner=runner,
                clear_cancelled=False,
            )
        while True:
            resolution = await wait_for_request_resolution(
                session_factory=configurable.get("session_factory"),
                child_run_id=child_run_id,
                request_id=request_id,
            )
            assistant_content = (
                resolution.request.assistant_content
                or resolution.child_run.last_assistant_content
            )
            if not assistant_content:
                raise ToolExecutionError(
                    "subagent turn completed without assistant content"
                )
            return assistant_content

    async def _execute(
        self,
        dispatch_id: str,
        prompt: str,
        background: bool = False,
    ) -> str:
        configurable = get_configurable(self.config)
        await ensure_primary(self._state, configurable.get("session_factory"))
        row = await resolve_child_run(
            parent_session_id=self.session_id,
            session_factory=configurable.get("session_factory"),
            dispatch_id=dispatch_id,
        )
        if not row.is_active:
            raise ToolExecutionError("subagent thread is inactive")
        current_revision_id = self._state.get("current_revision_id")
        parent_revision_id = (
            current_revision_id if isinstance(current_revision_id, str) else None
        )
        pre_request_checkpoint_id = await latest_checkpoint_id_for_thread(
            row.child_thread_id
        )

        session = await open_session(configurable.get("session_factory"))
        try:
            request_row = await enqueue_child_run_request(
                session,
                child_run_id=row.id,
                request_kind="notify",
                content=prompt,
                parent_revision_id=parent_revision_id,
                pre_request_checkpoint_id=pre_request_checkpoint_id,
                source_call=json.dumps(
                    [parent_revision_id, self.tool_call_id or generate_id()]
                ),
                background=background,
                persist_user_message=True,
                max_active_children=MAX_ACTIVE_SUBAGENTS,
            )
            child_user_message = await session.get(
                AgentRunMessage, request_row.child_user_message_id
            )
        except ChildRunCapacityError as exc:
            raise ToolExecutionError(str(exc), code="limit_exceeded") from exc
        except ChildRunReplayConflict as exc:
            raise ToolExecutionError(str(exc), code="conflict") from exc
        finally:
            await close_session(session)

        if child_user_message is not None:
            await publish_child_user_message(row.child_thread_id, child_user_message)

        runner = make_subagent_runner(state=self._state, configurable=configurable)
        await runner.publish_parent_subagent_status(row.id)
        pending_approval = getattr(row, "pending_approval_json", None)
        await emit_subagent_tool_preview(
            configurable=configurable,
            parent_session_id=self.session_id,
            tool_call_id=self.tool_call_id,
            tool_name=self.name,
            tool_args={
                "dispatch_id": dispatch_id,
                "prompt": prompt,
                **({"background": True} if background else {}),
            },
            row=row,
        )
        if background:
            return json.dumps(
                await start_background_request(
                    configurable=configurable,
                    parent_session_id=self.session_id,
                    row=row,
                    request_id=request_row.id,
                    runner=runner,
                ),
                ensure_ascii=False,
            )
        assistant_content = await self._wait_for_assistant_content(
            configurable=configurable,
            child_run_id=row.id,
            request_id=request_row.id,
            runner=runner,
            start_processing=request_row.status
            not in TERMINAL_CHILD_RUN_REQUEST_STATUSES
            and not (isinstance(pending_approval, dict) and pending_approval),
        )
        return json.dumps(
            {
                "dispatch_id": row.dispatch_id,
                "agent_number": (row.metadata_json or {}).get("agent_number"),
                "result": assistant_content,
            },
            ensure_ascii=False,
        )
