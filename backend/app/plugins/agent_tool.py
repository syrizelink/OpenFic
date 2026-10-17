"""Dynamic AgentTool adapter retaining existing approval and refresh hooks."""

import json
from typing import Any
from pydantic import Field
from app.agent_runtime.tools.base import AgentTool


class PluginAgentTool(AgentTool):
    args_schema: Any = Field(default_factory=dict)
    plugin_id: str
    command_name: str
    host: Any = Field(exclude=True)

    async def _execute(self, **params):
        from app.storage.database import create_session

        plugin = self.host.get(self.plugin_id)
        if (
            not plugin.registration
            or self.command_name not in plugin.registration.tools
        ):
            raise ValueError("Plugin tool is no longer active")
        session = self.get_runtime_db_session()
        owned = session is None
        if owned:
            session = await create_session()
        try:
            spec = plugin.registration.tools[self.command_name]
            import jsonschema

            jsonschema.validate(params, spec["schema"])
            context = self.host.context(self.plugin_id, session, self.runtime_state)
            result = await spec["handler"](context, params)
            await session.commit()
            return (
                result
                if isinstance(result, str)
                else json.dumps(result, ensure_ascii=False)
            )
        finally:
            if owned:
                await session.close()
