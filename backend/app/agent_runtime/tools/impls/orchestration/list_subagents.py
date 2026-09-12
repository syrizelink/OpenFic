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
    return f"{content[:500]}\n\n[Isi dipotong karena melebihi 500 karakter]"


class ListSubagentsInput(BaseModel):
    status: list[ChildRunStatus] | None = Field(
        default=None,
        description=dedent("""\
            Filter berdasarkan satu atau beberapa status; pilihannya queued, running,
            waiting_user, completed, error, cancelled.
            Biarkan kosong berarti tanpa filter
        """),
    )
    return_context: ReturnContext = Field(
        default="none",
        description=dedent("""\
            Apakah mengembalikan prompt dan result dari putaran interaksi terakhir;
            none berarti tidak dikembalikan, part berarti mengembalikan 500 karakter
            pertama, full berarti mengembalikan seluruh isi;
            gunakan full hanya bila benar-benar perlu, agar hasil yang terlalu panjang
            tidak menyebabkan konteks meluap.
        """),
    )
    model_config = {"extra": "forbid"}


@ToolRegistry.register
class ListSubagentsTool(AgentTool):
    name: str = "list_subagents"
    description: str = dedent("""\
        Menampilkan semua Subagent yang belum didaur ulang.
        Anda dapat memakai status untuk memfilter hasil, dan return_context untuk
        melihat isi putaran interaksi terakhir.
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
