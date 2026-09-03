from __future__ import annotations

import json
from textwrap import dedent

from pydantic import BaseModel, Field

from app.agent_runtime.persistence.child_runs import recycle_child_run
from app.agent_runtime.runner.checkpointer import delete_checkpoints_for_thread
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
    description: str = dedent("""\
        关闭一个Subagent会话
        使用时，必须指定dispatch_id来选定所要关闭的会话

        使用说明：
        - Subagent会话一旦被关闭就无法恢复
        - 仅在Subagent的任务已明确完成且后续不再需要它时才将其关闭，以免用户的后续指示需要时无法继续工作
        - 当处理完一个需求且用户确认通过或是要求开始完成下一个需求时，应及时关闭不再需要的Subagents
        - 对于只读而不做任何修改的Subagent，关闭会话通常是无影响的，可以在任务完成后关闭
        - 如果Subagent的描述中提到应在何时主动关闭，则尽力遵循，否则请自行判断
    """)
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
        await delete_checkpoints_for_thread(recycled.child_thread_id)

        runner = make_subagent_runner(state=self._state, configurable=configurable)
        await runner.publish_parent_subagent_status(recycled.id)
        return json.dumps(
            {
                "dispatch_id": recycled.dispatch_id,
                **build_subagent_identity_payload(recycled),
                "recycled": True,
            },
            ensure_ascii=False,
        )
