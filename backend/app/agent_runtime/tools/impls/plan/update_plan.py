from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app.agent_runtime.plan import service as plan_service
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.plan._shared import UpdatePlanInput
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session


def _todo_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    raise TypeError(f"不支持的 Todo 参数类型: {type(value)!r}")


@ToolRegistry.register
class UpdatePlanTool(AgentTool):
    name: str = "update_plan"
    description: str = "更新计划"
    access_level: str = "write"
    args_schema: type[BaseModel] = UpdatePlanInput

    async def _execute(
        self,
        plan_id: str,
        old_todos: list[Any],
        new_todos: list[Any],
    ) -> str:
        session = await create_session()
        try:
            plan = await plan_service.update_plan(
                session,
                runtime_state=self._state,
                plan_id=plan_id,
                old_todos=[_todo_payload(todo) for todo in old_todos],
                new_todos=[_todo_payload(todo) for todo in new_todos],
            )
            await session.commit()
            return json.dumps(
                {
                    "type": "ok",
                    "success": True,
                    "tool_name": self.name,
                    "plan": plan,
                    "message": "计划已更新",
                },
                ensure_ascii=False,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
