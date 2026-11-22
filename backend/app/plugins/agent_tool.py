"""Dynamic AgentTool adapter retaining existing approval and refresh hooks."""

import asyncio
import inspect
import json
from contextlib import suppress
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import Field

from app.agent_runtime.tools.base import AgentTool


class PluginAgentTool(AgentTool):
    args_schema: Any = Field(default_factory=dict)
    plugin_id: str
    command_name: str
    category: str
    display_name: str
    title: str
    icon: str | None = None
    message_detail: str | None = None
    host: Any = Field(exclude=True)

    async def _arun(
        self, *args: Any, config: RunnableConfig | None = None, **kwargs: Any
    ) -> str:
        from app.agent_runtime.tools.errors import ToolResult

        plugin = self.host.plugins.get(self.plugin_id)
        spec = (
            plugin.registration.tools.get(self.command_name)
            if plugin and plugin.registration
            else None
        )
        result = await super()._arun(*args, config=config, **kwargs)
        metadata = config.get("metadata", {}) if isinstance(config, dict) else {}
        if isinstance(metadata, dict) and metadata.get("openfic_phase") == "prepare":
            return result
        detail = spec.get("detail") if spec else None
        try:
            parsed = json.loads(result)
        except (TypeError, ValueError):
            parsed = str(result)
        try:
            if callable(detail):
                detail = detail(dict(kwargs), parsed)
                if inspect.isawaitable(detail):
                    async with asyncio.timeout(30):
                        detail = await detail
            if detail is not None and not isinstance(detail, str):
                raise ValueError("Tool detail must return a string or None")
        except Exception as error:
            with suppress(Exception):
                self.host._log(
                    self.plugin_id, "tool.detail", type(error).__name__, "warning"
                )
            detail = None
        if isinstance(result, ToolResult):
            payload = dict(result.payload)
        elif isinstance(parsed, dict):
            payload = dict(parsed)
        else:
            payload = {"success": True, "type": "ok", "data": parsed}
        payload["_openfic_plugin_tool"] = {
            "plugin_id": self.plugin_id,
            "icon": self.icon,
            "title": self.title,
            "detail": detail[:1024] if isinstance(detail, str) else None,
        }
        return ToolResult(str(result), payload)

    async def _execute(self, **params):
        async with self.host._lock:
            return await self._execute_locked(params)

    async def _execute_locked(self, params):
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
            context = self.host.context(
                self.plugin_id,
                session,
                {
                    **self.runtime_state,
                    "_runnable_config": self.config,
                    "_tool_call_id": self.tool_call_id,
                },
            )
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
