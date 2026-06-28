from __future__ import annotations

import json

from pydantic import BaseModel, Field, model_validator

from app.agent_runtime.persistence.child_runs import recycle_child_run
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.orchestration.common import (
    build_subagent_identity_payload,
    close_session,
    ensure_primary,
    get_configurable,
    make_subagent_runner,
    open_session,
    resolve_child_run,
)
from app.agent_runtime.tools.registry import ToolRegistry


class RecycleSubagentInput(BaseModel):
    child_run_id: str | None = Field(
        default=None,
        description="目标子代理运行 ID；与 dispatch_id 至少提供一个",
    )
    dispatch_id: str | None = Field(
        default=None,
        description="目标派发 ID；与 child_run_id 至少提供一个",
    )
    reason: str = Field(
        default="",
        description="可选关闭原因；会作为子代理回收时的错误/结束信息",
    )

    @model_validator(mode="after")
    def _validate_target(self) -> "RecycleSubagentInput":
        if not self.child_run_id and not self.dispatch_id:
            raise ValueError("child_run_id or dispatch_id is required")
        return self


@ToolRegistry.register
class RecycleSubagentTool(AgentTool):
    name: str = "recycle_subagent"
    description: str = (
        "关闭并回收一个 active 的子代理线程，关闭后该子代理上下文不可恢复，"
        "你将无法再向它 notify。应在子代理任务完成、且相关审查与验收均通过、"
        "确认不再需要其后续修改后再关闭；审查未通过前不要关闭，以免无法通知其返工。"
    )
    access_level: str = "readonly"
    args_schema: type[BaseModel] = RecycleSubagentInput

    async def _execute(
        self,
        child_run_id: str | None = None,
        dispatch_id: str | None = None,
        reason: str = "",
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
            return json.dumps(
                {
                    "tool_call_id": self.tool_call_id,
                    "child_run_id": row.id,
                    "dispatch_id": row.dispatch_id,
                    **build_subagent_identity_payload(row),
                    "recycled": True,
                },
                ensure_ascii=False,
            )

        await get_agent_run_registry().cancel_child(self.session_id, row.id)

        session = await open_session(configurable.get("session_factory"))
        try:
            recycled = await recycle_child_run(
                session,
                row.id,
                error=reason or None,
            )
        finally:
            await close_session(session)

        runner = make_subagent_runner(state=self._state, configurable=configurable)
        await runner.publish_parent_subagent_status(recycled.id)
        return json.dumps(
            {
                "tool_call_id": self.tool_call_id,
                "child_run_id": recycled.id,
                "dispatch_id": recycled.dispatch_id,
                **build_subagent_identity_payload(recycled),
                "recycled": True,
            },
            ensure_ascii=False,
        )
