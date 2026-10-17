"""Public Agent session control and context preparation facade."""

from langchain_core.messages import convert_to_messages


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
