from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.agent_runtime.persistence.child_runs import enqueue_child_run_request
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.orchestration.common import (
    build_subagent_identity_payload,
    close_session,
    ensure_child_processing,
    ensure_primary,
    get_configurable,
    make_subagent_runner,
    open_session,
    persist_child_user_message,
    resolve_child_run,
    wait_for_request_resolution,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.core.ids import generate_id


class NotifySubagentInput(BaseModel):
    child_run_id: str | None = Field(
        default=None,
        description="目标子代理运行 ID；与 dispatch_id 至少提供一个",
    )
    dispatch_id: str | None = Field(
        default=None,
        description="目标派发 ID；与 child_run_id 至少提供一个",
    )
    message: str = Field(
        min_length=1,
        description="发送给现有子代理线程的后续消息内容",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="附加元数据，会随本次通知请求一同持久化",
    )

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate_target(self) -> "NotifySubagentInput":
        if not self.child_run_id and not self.dispatch_id:
            raise ValueError("child_run_id or dispatch_id is required")
        return self


@ToolRegistry.register
class NotifySubagentTool(AgentTool):
    name: str = "notify_subagent"
    description: str = (
        "向一个仍处于 active 状态的子代理线程发送后续消息，并阻塞等待该消息产出回复。"
        "用于在子代理已有上下文的基础上继续追问、补充要求或通知其修改，"
        "无需重新 dispatch。目标子代理必须仍未被回收。"
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
                raise ToolExecutionError("subagent turn completed without assistant content")
            return assistant_content

    async def _execute(
        self,
        child_run_id: str | None = None,
        dispatch_id: str | None = None,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        ensure_primary(self._state)
        configurable = get_configurable(self.config)
        row = await resolve_child_run(
            parent_session_id=self.session_id,
            session_factory=configurable.get("session_factory"),
            child_run_id=child_run_id,
            dispatch_id=dispatch_id,
        )
        if not row.is_active:
            raise ToolExecutionError("subagent thread is inactive")
        tool_call_id = self.tool_call_id or generate_id()

        session = await open_session(configurable.get("session_factory"))
        try:
            request_row = await enqueue_child_run_request(
                session,
                child_run_id=row.id,
                request_kind="notify",
                content=message,
            )
        finally:
            await close_session(session)

        await persist_child_user_message(
            session_factory=configurable.get("session_factory"),
            child_thread_id=row.child_thread_id,
            task_id=str(self._state["task_id"]),
            project_id=str(self._state["project_id"]),
            content=message,
        )

        runner = make_subagent_runner(state=self._state, configurable=configurable)
        await runner.publish_parent_subagent_status(row.id)
        pending_approval = getattr(row, "pending_approval_json", None)
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
                "tool_call_id": tool_call_id,
                "child_run_id": row.id,
                "dispatch_id": row.dispatch_id,
                **build_subagent_identity_payload(row),
                "assistant_content": assistant_content,
            },
            ensure_ascii=False,
        )
