from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.agent_runtime.persistence.child_runs import (
    enqueue_child_run_request,
    update_child_run_request_boundaries,
)
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
    persist_child_user_message,
    resolve_child_run,
    wait_for_request_resolution,
)
from app.agent_runtime.tools.registry import ToolRegistry


class NotifySubagentInput(BaseModel):
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
    description: str = (
        "向一个 subagent 会话发送消息来恢复进程"
        "使用 notify 工具时，必须指定一个 active 会话的 dispatch_id 来选定所要继续的进程"
        ""
        "使用说明："
        "- 恢复的 subagent 会话沿用此前完成时的状态（消息历史、工具输出等），不要提供重复的上下文信息"
        "- 继续会话时，聚焦于当前任务，明确说明下一步的要求"
        "- 一个 subagent 会话被 recycle 后，dispatch_id 就会失效无法使用"
    )
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
            )
        finally:
            await close_session(session)

        child_user_message = await persist_child_user_message(
            session_factory=configurable.get("session_factory"),
            child_thread_id=row.child_thread_id,
            task_id=str(self._state["task_id"]),
            project_id=str(self._state["project_id"]),
            content=prompt,
        )
        session = await open_session(configurable.get("session_factory"))
        try:
            await update_child_run_request_boundaries(
                session,
                request_row.id,
                child_user_message_id=child_user_message.id,
                child_user_message_seq=child_user_message.seq,
            )
        finally:
            await close_session(session)

        runner = make_subagent_runner(state=self._state, configurable=configurable)
        await runner.publish_parent_subagent_status(row.id)
        pending_approval = getattr(row, "pending_approval_json", None)
        await emit_subagent_tool_preview(
            configurable=configurable,
            parent_session_id=self.session_id,
            tool_call_id=self.tool_call_id,
            tool_name=self.name,
            tool_args={"dispatch_id": dispatch_id, "prompt": prompt},
            row=row,
        )
        assistant_content = await self._wait_for_assistant_content(
            configurable=configurable,
            child_run_id=row.id,
            request_id=request_row.id,
            runner=runner,
            start_processing=not (
                isinstance(pending_approval, dict) and pending_approval
            ),
        )
        return json.dumps(
            {
                "dispatch_id": row.dispatch_id,
                "agent_number": (row.metadata_json or {}).get("agent_number"),
                "result": assistant_content,
            },
            ensure_ascii=False,
        )
