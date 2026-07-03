from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.agent_runtime.agents.definitions import (
    AgentDefinition,
    load_agent_definition,
)
from app.agent_runtime.persistence.child_runs import (
    create_child_run,
    get_child_run_request_by_seq,
    get_running_child_run_request,
    get_waiting_child_run_for_tool_call,
    update_child_run_request_boundaries,
)
from app.agent_runtime.runner.checkpointer import latest_checkpoint_id_for_thread
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.orchestration.common import (
    build_subagent_identity_payload,
    close_session,
    ensure_child_processing,
    get_configurable,
    make_subagent_runner,
    open_session,
    persist_child_user_message,
    wait_for_request_resolution,
)
from app.agent_runtime.tools.registry import ToolRegistry
from app.core.ids import generate_id


MAX_DISPATCHES_PER_TURN = 10


class DispatchSubagentInput(BaseModel):
    agent_key: str = Field(
        description="要委派的子代理标识",
    )
    task: str = Field(
        min_length=1,
        description=(
            "发给子代理的任务说明，须自包含且明确，至少覆盖："
            "TASK 原子目标、"
            "EXPECTED OUTCOME 交付物与成功标准、"
            "MUST DO 必须做的事、"
            "MUST NOT DO 禁止的操作、"
            "CONTEXT 相关信息索引"
        ),
    )
    input: dict[str, Any] = Field(
        default_factory=dict,
        description="传给子代理的结构化输入数据",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="附加元数据，会随本次委派请求一同持久化",
    )

    model_config = {"extra": "forbid"}


def _child_thread_id(parent_thread_id: str, dispatch_id: str) -> str:
    return f"{parent_thread_id}:child:{dispatch_id}"[:128]


@ToolRegistry.register
class DispatchSubagentTool(AgentTool):
    name: str = "dispatch_subagent"
    description: str = (
        "委派一个子代理执行任务并阻塞等待其返回结果。"
        "每轮最多调用10次，达到上限后需先使用 recycle_subagent 关闭不再需要的子代理。"
        "调用本工具会等待子代理结束当前轮次，期间无法并行其它工作。"
    )
    access_level: str = "readonly"
    args_schema: type[BaseModel] = DispatchSubagentInput

    async def _load_definition(
        self,
        agent_key: str,
        configurable: dict[str, Any],
    ) -> AgentDefinition:
        session = await open_session(configurable.get("session_factory"))
        try:
            return await load_agent_definition(session, agent_key)
        finally:
            await close_session(session)

    async def _validate_dispatch(
        self,
        agent_key: str,
        configurable: dict[str, Any],
    ) -> None:
        active_agent = self._state.get("active_agent")
        if not isinstance(active_agent, str) or not active_agent:
            raise ToolExecutionError("dispatch_subagent may only be called by primary")

        try:
            primary_def = await self._load_definition(active_agent, configurable)
        except KeyError:
            primary_def = None
        if primary_def is None or primary_def.kind != "primary":
            raise ToolExecutionError("dispatch_subagent may only be called by primary")

        count = int(self._state.get("_dispatch_subagent_count") or 0)
        if count >= MAX_DISPATCHES_PER_TURN:
            raise ToolExecutionError("dispatch_subagent allows at most 10 dispatches per PA turn")
        self._state["_dispatch_subagent_count"] = count + 1

        try:
            definition = await self._load_definition(agent_key, configurable)
        except KeyError as exc:
            raise ToolExecutionError(f"unknown subagent: {agent_key}") from exc
        if not definition.enabled or definition.kind != "subagent":
            raise ToolExecutionError(f"agent is not an enabled subagent: {agent_key}")

        if primary_def.delegatable_agents:
            if agent_key not in primary_def.delegatable_agents:
                raise ToolExecutionError(
                    f"agent '{agent_key}' is not in the delegatable agents whitelist"
                )

    async def _create_child_run(
        self,
        *,
        agent_key: str,
        task: str,
        input: dict[str, Any],
        metadata: dict[str, Any],
        configurable: dict[str, Any],
        tool_call_id: str,
    ):
        dispatch_id = generate_id()
        parent_thread_id = str(configurable.get("thread_id") or self.session_id)
        child_thread_id = _child_thread_id(parent_thread_id, dispatch_id)
        session = await open_session(configurable.get("session_factory"))
        try:
            return await create_child_run(
                session,
                parent_session_id=self.session_id,
                parent_task_id=str(self._state["task_id"]),
                parent_thread_id=parent_thread_id,
                child_thread_id=child_thread_id,
                agent_key=agent_key,
                dispatch_id=dispatch_id,
                tool_call_id=tool_call_id,
                request={"task": task, "input": input, "metadata": metadata},
                metadata={"tool_metadata": metadata},
                parent_revision_id=self._state.get("current_revision_id")
                if isinstance(self._state.get("current_revision_id"), str)
                else None,
            )
        finally:
            await close_session(session)

    async def _load_waiting_child_run(
        self,
        *,
        configurable: dict[str, Any],
        tool_call_id: str,
    ):
        session = await open_session(configurable.get("session_factory"))
        try:
            return await get_waiting_child_run_for_tool_call(
                session,
                parent_session_id=self.session_id,
                tool_call_id=tool_call_id,
            )
        finally:
            await close_session(session)

    async def _load_initial_request_id(
        self,
        *,
        configurable: dict[str, Any],
        child_run_id: str,
    ) -> str:
        session = await open_session(configurable.get("session_factory"))
        try:
            request_row = await get_child_run_request_by_seq(
                session,
                child_run_id=child_run_id,
                seq=0,
            )
            if request_row is None:
                raise ToolExecutionError("initial subagent request not found")
            return request_row.id
        finally:
            await close_session(session)

    async def _load_running_request_id(
        self,
        *,
        configurable: dict[str, Any],
        child_run_id: str,
    ) -> str:
        session = await open_session(configurable.get("session_factory"))
        try:
            request_row = await get_running_child_run_request(
                session,
                child_run_id=child_run_id,
            )
            if request_row is None:
                raise ToolExecutionError("active subagent request not found")
            return request_row.id
        finally:
            await close_session(session)

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
        agent_key: str,
        task: str,
        input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        configurable = get_configurable(self.config)
        await self._validate_dispatch(agent_key, configurable)
        input = input or {}
        metadata = metadata or {}
        tool_call_id = self.tool_call_id or generate_id()
        row = await self._load_waiting_child_run(
            configurable=configurable,
            tool_call_id=tool_call_id,
        )
        request_id = None
        if row is not None:
            request_id = await self._load_running_request_id(
                configurable=configurable,
                child_run_id=row.id,
            )
        if row is None:
            row = await self._create_child_run(
                agent_key=agent_key,
                task=task,
                input=input,
                metadata=metadata,
                configurable=configurable,
                tool_call_id=tool_call_id,
            )
            pre_request_checkpoint_id = await latest_checkpoint_id_for_thread(
                row.child_thread_id
            )
            child_user_message = await persist_child_user_message(
                session_factory=configurable.get("session_factory"),
                child_thread_id=row.child_thread_id,
                task_id=str(self._state["task_id"]),
                project_id=str(self._state["project_id"]),
                content=task,
            )
            request_id = await self._load_initial_request_id(
                configurable=configurable,
                child_run_id=row.id,
            )
            session = await open_session(configurable.get("session_factory"))
            try:
                await update_child_run_request_boundaries(
                    session,
                    request_id,
                    child_user_message_id=child_user_message.id,
                    child_user_message_seq=child_user_message.seq,
                    pre_request_checkpoint_id=pre_request_checkpoint_id,
                )
            finally:
                await close_session(session)
        runner = make_subagent_runner(state=self._state, configurable=configurable)
        await runner.publish_parent_subagent_status(row.id)

        base_payload = {
            "tool_call_id": tool_call_id,
            "dispatch_id": row.dispatch_id,
            "child_run_id": row.id,
            "child_thread_id": row.child_thread_id,
            "is_active": row.is_active,
            **build_subagent_identity_payload(row),
        }

        pending_approval = getattr(row, "pending_approval_json", None)
        assistant_content = await self._wait_for_assistant_content(
            configurable=configurable,
            child_run_id=row.id,
            request_id=request_id or "",
            runner=runner,
            start_processing=not (
                isinstance(pending_approval, dict) and pending_approval
            ),
        )
        payload = {
            **base_payload,
            "assistant_content": assistant_content,
        }
        return json.dumps(payload, ensure_ascii=False)
