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
    agent_type: str = Field(
        description="委派用于处理当前任务的专用 agent 类型",
    )
    description: str = Field(
        min_length=1,
        description="任务的简短描述，应简洁明了，20字以内",
    )
    prompt: str = Field(
        min_length=1,
        description=(
            "要 agent 执行的任务描述，应是自包含且明确的，至少覆盖："
            "- TASK 对任务的描述"
            "- GOAL 原子目标"
            "- EXPECTED OUTCOME 交付物与成功标准"
            "- MUST DO 必须完成的工作"
            "- MUST NOT DO 禁止的操作"
            "- CONTEXT 相关信息索引"
        ),
    )
    model_config = {"extra": "forbid"}


def _child_thread_id(parent_thread_id: str, dispatch_id: str) -> str:
    return f"{parent_thread_id}:child:{dispatch_id}"[:128]


@ToolRegistry.register
class DispatchSubagentTool(AgentTool):
    name: str = "dispatch_subagent"
    description: str = (
        "委派一个新的 agent 处理复杂、多步骤的任务。"
        "使用 dispatch 工具时，必须指定 agent_type 参数来选定要使用的 subagent 类型。"
        ""
        "何时不应使用："
        "- 在特定章节或2-3个章节或设定中搜索信息"
        "- 没有合适的 agent 准确对应任务类型"
        "- 用户明确要求不使用子代理时"
        ""
        "何时使用："
        "- 需要并行处理多个独立任务，提升效率"
        "- 任务复杂度高、专业性强，需要使用专业的 agent 针对性处理"
        "- 需要隔离上下文，只想了解特定信息却不想查找一遍整个项目"
        ""
        "使用说明："
        "- 尽可能并发启动多个 agent 处理任务以提高效率，为此只需在一轮消息多次调用工具即可"
        "- agent 完成后会在工具结果中返回，agent 的执行结果对用户不可见，如要向用户展示执行结果，你应输出一段简短的总结"
        "- agent 的执行结果包含 dispatch_id，可在后续通过 notify_subagent 复用以继续同一 agent 会话"
        "- agent 的执行结果中包含 agent_number，每个 agent 都有唯一的编号，如有需要你可以用编号来称呼它们"
        "- 每次派发的 agent 都从独立全新的上下文，因此 agent 并不了解你所持有的信息或过去完成的任务"
        "- 派发 agent 时，应在 prompt 中包含详尽、具体、可执行的任务描述，并明确指示 agent 应在任务完成时返回什么信息，因为它并不了解用户意图"
        "- 一般情况下应信任 agent 的输出"
        "- 如果 agent 描述中提到应主动使用它们，则尽力使用，而无需用户明确指示，否则请自行判断"
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
        description: str,
        task: str,
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
                request={"description": description, "task": task},
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
        agent_type: str,
        description: str,
        prompt: str,
    ) -> str:
        configurable = get_configurable(self.config)
        await self._validate_dispatch(agent_type, configurable)
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
                agent_key=agent_type,
                description=description,
                task=prompt,
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
                content=prompt,
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
            "dispatch_id": row.dispatch_id,
            "agent_number": (row.metadata_json or {}).get("agent_number"),
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
            "result": assistant_content,
        }
        return json.dumps(payload, ensure_ascii=False)
