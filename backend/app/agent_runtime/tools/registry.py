from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent_runtime.tools.base import AgentTool, ToolBuildHook, ToolHook


class ToolRegistry:
    _tools: dict[str, type[AgentTool]] = {}

    @classmethod
    def register(cls, tool_class: type[AgentTool]) -> type[AgentTool]:
        cls._tools[tool_class.model_fields["name"].default] = tool_class
        return tool_class

    @classmethod
    def get_tools(
        cls,
        names: list[str] | None = None,
        *,
        state: dict,
        build_hooks: list[ToolBuildHook] | None = None,
        pre_hooks: list[ToolHook] | None = None,
        post_hooks: list[ToolHook] | None = None,
    ) -> list[AgentTool]:
        target_names = names if names is not None else list(cls._tools.keys())
        tools = []
        for name in target_names:
            if name not in cls._tools:
                raise KeyError(f"Tool not registered: {name}")
            tool_cls = cls._tools[name]
            instance = tool_cls(
                _state=state,
                _pre_hooks=pre_hooks or [],
                _post_hooks=post_hooks or [],
            )
            for hook in build_hooks or []:
                hook(instance)
            tools.append(instance)
        return tools

    @classmethod
    def list_names(cls) -> list[str]:
        return list(cls._tools.keys())
