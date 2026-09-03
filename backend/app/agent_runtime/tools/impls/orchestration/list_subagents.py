from __future__ import annotations

import json
from textwrap import dedent
from typing import Literal

from pydantic import BaseModel, Field

from app.agent_runtime.persistence.child_runs import (
    TERMINAL_CHILD_RUN_REQUEST_STATUSES,
    get_child_run_agent_number,
    get_latest_child_run_requests,
    list_child_runs_for_parent,
)
from app.agent_runtime.tools.base import AgentTool
from app.agent_runtime.tools.impls.orchestration.common import (
    close_session,
    ensure_primary,
    get_configurable,
    open_session,
)
from app.agent_runtime.tools.registry import ToolRegistry


ChildRunStatus = Literal[
    "queued",
    "running",
    "waiting_user",
    "completed",
    "error",
    "cancelled",
]
ReturnContext = Literal["none", "part", "full"]


def _format_context(content: str, return_context: ReturnContext) -> str:
    if return_context == "full" or len(content) <= 500:
        return content
    return f"{content[:500]}\n\n[内容因超出 500 字符被截断]"


class ListSubagentsInput(BaseModel):
    status: list[ChildRunStatus] | None = Field(
        default=None,
        description=dedent("""\
            按一个或多个状态过滤；可选queued、running、waiting_user、completed、error、cancelled，
            留空表示不过滤
        """),
    )
    return_context: ReturnContext = Field(
        default="none",
        description=dedent("""\
            是否返回最后一轮交互的prompt和result；
            none表示不返回，part表示返回前500个字符，full表示返回全部内容；
            仅在必要时使用full，以避免过长的结果导致上下文溢出。
        """),
    )
    model_config = {"extra": "forbid"}


@ToolRegistry.register
class ListSubagentsTool(AgentTool):
    name: str = "list_subagents"
    description: str = dedent("""\
        列出所有未被回收的Subagent。
        可使用status过滤结果，并使用return_context查看最后一轮交互内容。
    """)
    access_level: str = "readonly"
    args_schema: type[BaseModel] = ListSubagentsInput

    async def _execute(
        self,
        status: list[ChildRunStatus] | None = None,
        return_context: ReturnContext = "none",
    ) -> str:
        configurable = get_configurable(self.config)
        await ensure_primary(self._state, configurable.get("session_factory"))

        session = await open_session(configurable.get("session_factory"))
        try:
            rows = await list_child_runs_for_parent(
                session,
                self.session_id,
                is_active=True,
                statuses=status or None,
            )
            latest_requests = (
                await get_latest_child_run_requests(
                    session,
                    [row.id for row in rows],
                )
                if return_context != "none"
                else {}
            )
        finally:
            await close_session(session)

        payload = []
        for row in rows:
            subagent = {
                "dispatch_id": row.dispatch_id,
                "agent_key": row.agent_key,
                "agent_number": get_child_run_agent_number(row.metadata_json),
                "status": row.status,
            }
            if return_context != "none":
                latest_request = latest_requests.get(row.id)
                if latest_request is not None:
                    subagent["prompt"] = _format_context(
                        latest_request.content,
                        return_context,
                    )
                    if (
                        latest_request.status in TERMINAL_CHILD_RUN_REQUEST_STATUSES
                        and latest_request.assistant_content is not None
                    ):
                        subagent["result"] = _format_context(
                            latest_request.assistant_content,
                            return_context,
                        )
            payload.append(subagent)
        return json.dumps(payload, ensure_ascii=False)
