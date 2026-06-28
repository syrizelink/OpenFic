from __future__ import annotations

import json

from pydantic import BaseModel

from app.agent_runtime.plan import service as plan_service
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.plan._shared import ListPlanInput
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session


@ToolRegistry.register
class ListPlanTool(AgentTool):
    name: str = "list_plan"
    description: str = "列出全部计划。"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ListPlanInput

    async def _execute(self) -> str:
        session = await create_session()
        try:
            plans = await plan_service.list_plans(
                session,
                runtime_state=self._state,
            )
            return json.dumps(
                {
                    "type": "ok",
                    "success": True,
                    "tool_name": self.name,
                    "plans": plans,
                    "message": "计划列表读取成功",
                },
                ensure_ascii=False,
            )
        finally:
            await session.close()
