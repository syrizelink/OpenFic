from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app.agent_runtime.plan import service as plan_service
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.plan._shared import CreatePlanInput
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session


def _todo_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    raise TypeError(f"不支持的 Todo 参数类型: {type(value)!r}")


@ToolRegistry.register
class CreatePlanTool(AgentTool):
    name: str = "create_plan"
    description: str = "创建一个计划"
    access_level: str = "write"
    args_schema: type[BaseModel] = CreatePlanInput

    async def _execute(
        self,
        topic: str,
        description: str,
        parent_dependency_todo_id: str | None = None,
        todos: list[Any] | None = None,
    ) -> str:
        session = await create_session()
        try:
            plan = await plan_service.create_plan(
                session,
                runtime_state=self._state,
                topic=topic,
                description=description,
                parent_dependency_todo_id=parent_dependency_todo_id,
                todos=[_todo_payload(todo) for todo in (todos or [])],
            )
            await session.commit()
            return json.dumps(
                {
                    "type": "ok",
                    "success": True,
                    "tool_name": self.name,
                    "plan": plan,
                    "message": "计划已创建",
                },
                ensure_ascii=False,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
