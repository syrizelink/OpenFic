from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.agent_runtime.persistence.child_runs import recycle_child_run
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.orchestration.common import (
    close_session,
    ensure_primary,
    get_configurable,
    make_subagent_runner,
    open_session,
    resolve_child_run,
)
from app.agent_runtime.tools.registry import ToolRegistry


class RecycleSubagentInput(BaseModel):
    dispatch_id: str = Field(
        min_length=1,
        description="subagent 会话ID",
    )
    reason: str = Field(
        default="",
        description="可选，关闭原因；会作为子代理回收时的错误/结束信息，对用户可见，应尽可能简要",
    )

@ToolRegistry.register
class RecycleSubagentTool(AgentTool):
    name: str = "recycle_subagent"
    description: str = (
        "关闭一个 active 的 subagent 会话"
        "使用 notify 工具时，必须指定一个 active 会话的 dispatch_id 来选定所要继续的进程"
        ""
        "使用说明："
        "- subagent 会话一旦被关闭就无法恢复"
        "- 一般情况下不需要关闭 subagent 会话，以免用户的后续指示需要时无法继续工作"
        "- 对于只读而不做任何修改的 agent，关闭会话通常是无影响的，可以在任务完成且不再需要后关闭"
        "- 如果 agent 描述中提到应在任务完成后主动关闭，则尽力遵循，否则请自行判断"
    )
    access_level: str = "readonly"
    args_schema: type[BaseModel] = RecycleSubagentInput

    async def _execute(
        self,
        dispatch_id: str,
        reason: str = "",
    ) -> str:
        configurable = get_configurable(self.config)
        await ensure_primary(self._state, configurable.get("session_factory"))
        row = await resolve_child_run(
            parent_session_id=self.session_id,
            session_factory=configurable.get("session_factory"),
            dispatch_id=dispatch_id,
        )
        if not row.is_active:
            return json.dumps(
                {
                    "dispatch_id": row.dispatch_id,
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
                "dispatch_id": recycled.dispatch_id,
                "recycled": True,
            },
            ensure_ascii=False,
        )
