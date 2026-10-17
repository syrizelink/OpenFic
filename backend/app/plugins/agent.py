"""Public Agent session control and context preparation facade."""

from langchain_core.messages import convert_to_messages
from langchain_core.runnables import RunnableConfig


class PluginAgent:
    def __init__(self, context):
        self.context = context

    async def start(self, project_id, model_id, **options):
        self.context.require("agent.invoke")
        return await self.context.api.request(
            "POST",
            "/agent/sessions",
            json={"project_id": project_id, "model_id": model_id, **options},
        )

    async def send(self, session_id, message, **options):
        self.context.require("agent.invoke")
        return await self.context.api.request(
            "POST",
            f"/agent/sessions/{session_id}/message",
            json={"message": message, **options},
        )

    async def cancel(self, session_id):
        self.context.require("agent.invoke")
        return await self.context.api.request(
            "POST", f"/agent/sessions/{session_id}/cancel"
        )

    def tools(self):
        self.context.require("agent.invoke")
        from app.agent_runtime.tools import ToolRegistry

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "access_level": tool.access_level,
                "inputSchema": tool.args_schema
                if isinstance(tool.args_schema, dict)
                else tool.args_schema.model_json_schema(),
            }
            for tool in ToolRegistry.get_tools(state=self.context.runtime)
            if not tool.name.startswith("plugin_")
        ]

    async def call_tool(self, name: str, arguments: dict):
        """Use built-in versioned tools from an active plugin Agent tool.

        Nested calls retain approval and change journaling. Their model-facing
        tool result belongs to the outer plugin tool, so callbacks are suppressed.
        """
        self.context.require("agent.invoke")
        state = self.context.runtime
        if not state.get("current_revision_id") or not state.get("session_id"):
            raise ValueError(
                "Built-in tool execution requires an active versioned Agent session"
            )
        from app.agent_runtime.tools import ToolRegistry

        if name.startswith("plugin_") or name not in ToolRegistry._tools:
            raise ValueError("Only built-in tools can be called through this interface")
        from app.agent_runtime.tools.hooks.auth import auth_hook
        from app.agent_runtime.tools.hooks.chapter_refresh import (
            chapter_refresh_post_hook,
        )
        from app.agent_runtime.tools.hooks.note_refresh import note_refresh_post_hook
        from app.agent_runtime.tools.hooks.world_entry_refresh import (
            world_entry_refresh_post_hook,
        )
        from app.agent_runtime.tools.hooks.character_refresh import (
            character_refresh_post_hook,
        )

        tool = next(
            tool
            for tool in ToolRegistry.get_tools(
                names=[name],
                state=state,
                pre_hooks=[auth_hook],
                post_hooks=[
                    chapter_refresh_post_hook,
                    note_refresh_post_hook,
                    world_entry_refresh_post_hook,
                    character_refresh_post_hook,
                ],
            )
            if tool.name == name
        )
        import json

        configuration = self.context._private_runtime.get("_runnable_config") or {}
        config: RunnableConfig = {
            **configuration,
            "callbacks": [],
            "metadata": {
                **{
                    key: value
                    for key, value in configuration.get("metadata", {}).items()
                    if key
                    not in {"openfic_phase", "openfic_skip_pre_hooks", "tool_call"}
                },
                "tool_call_id": self.context._private_runtime.get("_tool_call_id"),
            },
            "configurable": {
                **configuration.get("configurable", {}),
                "db_session": self.context.data._session,
            },
        }
        result = await tool.ainvoke(arguments, config=config)
        try:
            parsed = json.loads(result)
        except (ValueError, TypeError):
            return result
        if isinstance(parsed, dict) and parsed.get("success") is False:
            raise ValueError(
                parsed.get("message") or parsed.get("error") or "Built-in tool failed"
            )
        return parsed

    async def context_messages(self, messages, *, builtin=True):
        self.context.require("agent.hooks")
        from app.plugins.runtime import model_messages

        context = self.context
        prepared = convert_to_messages(messages)
        runtime = context.runtime
        if builtin and runtime.get("model_config", {}).get("max_context_tokens"):
            from app.agent_runtime.context.build_context import build_context
            from app.agent_runtime.graph.react_agent import _to_history_dict

            prepared = await build_context(
                runtime,
                runtime.get("agent_key", "build"),
                [_to_history_dict(m) for m in prepared],
                context.data._session,
            )
        return await model_messages(
            prepared, context.data._session, runtime=runtime, host=context.host
        )
