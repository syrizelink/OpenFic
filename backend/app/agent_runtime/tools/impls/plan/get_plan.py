from __future__ import annotations

import json

from pydantic import BaseModel

from app.agent_runtime.plan import service as plan_service
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.plan._shared import GetPlanInput
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session


@ToolRegistry.register
class GetPlanTool(AgentTool):
    name: str = "get_plan"
    description: str = "读取指定计划"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = GetPlanInput

    async def _execute(self, plan_id: str) -> str:
        session = await create_session()
        try:
            plan = await plan_service.get_plan(
                session,
                runtime_state=self._state,
                plan_id=plan_id,
            )
            return json.dumps(
                {
                    "type": "ok",
                    "success": True,
                    "tool_name": self.name,
                    "plan": plan,
                    "message": "计划读取成功",
                },
                ensure_ascii=False,
            )
        finally:
            await session.close()
