from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app.agent_runtime.plan import service as plan_service
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.plan._shared import WritePlanInput
from app.agent_runtime.tools.registry import ToolRegistry
from app.storage.database import create_session


def _todo_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    raise TypeError(f"不支持的 Todo 参数类型: {type(value)!r}")


@ToolRegistry.register
class WritePlanTool(AgentTool):
    name: str = "write_plan"
    description: str = (
        "全量覆盖当前会话的计划 Todo 列表。每次调用都必须传入完整列表。"
        "为当前会话创建并维护结构化的任务列表，用于追踪进度、组织复杂、多步骤的工作，并向用户展示进度。"
        ""
        "何时使用："
        "- 任务需要 3+ 个不同步骤或动作（注意，此处指的不仅仅是三次工具调用）"
        "- 任务足够复杂，通过规划能够更好的组织和执行"
        "- 用户提供了多个任务需求，或是明确要求使用计划"
        "- 收到新需求 —— 将其拆解并记录为 Todo 列表"
        "- 开始任务 —— 在开始实施前标记当前 todo 项为 in_progress"
        "- 完成任务 —— 标记当前 todo 项为 completed，并根据工作期间的实际发现更新或添加后续项"
        ""
        "何时不应使用："
        "- 单一、直接的简单任务，无需规划即可直接执行"
        "- 任务步骤琐碎且简单(<3 个)"
        "- 用户需求属于讨论或对话性质"
        "- 计划对组织当前任务没有价值"
        ""
        "状态："
        "- pending: 待办，尚未开始"
        "- in_progress: 进行中，当前正在执行(仅一个)"
        "- completed: 已成功完成"
        ""
        "优先级："
        "- low: 低优先级，可延后处理"
        "- medium: 中等优先级，正常处理"
        "- high: 高优先级，优先处理"
        ""
        "使用说明："
        "- 实时更新任务状态，开始或完成前立刻更新，不要留到最后批量更新"
        "- 仅在 todo 项对应的工作实际完成(包括验证和审批，如必要)后才标记为 completed"
        "- 同时仅标记恰好一个 in_progress 状态的 todo 项"
        "- 任务受阻或部分完成的情况下，可以保持阻塞的 todo 项为 in_progress，更新后续计划以适应当前状况并继续"
        "- 每个 todo 项都应是具体、可操作的独立子任务"
    )
    access_level: str = "write"
    args_schema: type[BaseModel] = WritePlanInput

    async def _execute(self, todos: list[Any]) -> str:
        session = await create_session()
        try:
            await plan_service.write_plan(
                session,
                runtime_state=self._state,
                todos=[_todo_payload(todo) for todo in todos],
            )
            await session.commit()
            return json.dumps(
                {
                    "success": True,
                },
                ensure_ascii=False,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
