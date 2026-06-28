from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeAlias, cast

from langchain_core.runnables.config import var_child_runnable_config
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools.errors import ToolExecutionError


def _validation_error_to_json(error: object) -> str:
    return json.dumps({"error": f"参数校验失败: {error}"}, ensure_ascii=False)


@dataclass
class HookContext:
    tool_name: str
    access_level: str
    args: dict[str, Any]
    state: dict[str, Any]
    config: RunnableConfig | None = None
    tool_call_id: str | None = None
    output: str | None = None


@dataclass
class HookResult:
    proceed: bool = True
    interrupt_payload: dict[str, Any] | None = None
    output: str | None = None


ToolHook: TypeAlias = Callable[[HookContext], Awaitable[HookResult]]
ToolBuildHook: TypeAlias = Callable[["AgentTool"], None]


class AgentTool(BaseTool):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    access_level: str = "write"
    name: str = ""
    description: str = ""
    args_schema: type[BaseModel] = BaseModel
    handle_validation_error = staticmethod(_validation_error_to_json)

    runtime_state: dict[str, Any] = Field(
        default_factory=dict,
        alias="_state",
        exclude=True,
        repr=False,
    )
    pre_hooks: list[ToolHook] = Field(
        default_factory=list,
        alias="_pre_hooks",
        exclude=True,
        repr=False,
    )
    post_hooks: list[ToolHook] = Field(
        default_factory=list,
        alias="_post_hooks",
        exclude=True,
        repr=False,
    )
    _config: RunnableConfig | None = None
    _tool_call_id: str | None = None

    @property
    def _state(self) -> dict[str, Any]:
        return self.runtime_state

    @property
    def _pre_hooks(self) -> list[ToolHook]:
        return self.pre_hooks

    @property
    def _post_hooks(self) -> list[ToolHook]:
        return self.post_hooks

    @property
    def project_id(self) -> str:
        return self.runtime_state["project_id"]

    @property
    def session_id(self) -> str:
        return self.runtime_state["session_id"]

    @property
    def tool_call_id(self) -> str | None:
        return getattr(self, "_tool_call_id", None)

    @property
    def config(self) -> RunnableConfig | None:
        return getattr(self, "_config", None)

    def get_runtime_db_session(self) -> AsyncSession | None:
        config = self.config
        if not isinstance(config, dict):
            return None
        configurable = config.get("configurable") or {}
        if not isinstance(configurable, dict):
            return None
        return cast(AsyncSession | None, configurable.get("db_session"))

    async def build_interrupt_preview(
        self,
        args: dict[str, Any],
    ) -> dict[str, Any] | None:
        return None

    async def _finalize_interrupt_payload(
        self,
        interrupt_payload: dict[str, Any] | None,
        *,
        args: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not isinstance(interrupt_payload, dict):
            return interrupt_payload
        if interrupt_payload.get("type") != "tool_approval":
            return interrupt_payload

        payload = dict(interrupt_payload)
        if self.tool_call_id and "tool_call_id" not in payload:
            payload["tool_call_id"] = self.tool_call_id

        if payload.get("denied") is True:
            return payload

        preview = await self.build_interrupt_preview(args)
        if preview is not None:
            payload["tool_result_preview"] = preview
        return payload

    async def _arun(
        self,
        *args: Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> str:
        runtime_config = config
        if runtime_config is None:
            context_config = var_child_runnable_config.get()
            runtime_config = context_config if isinstance(context_config, dict) else None
        validated_args = dict(kwargs)
        metadata = runtime_config.get("metadata") if isinstance(runtime_config, dict) else None
        metadata_dict = metadata if isinstance(metadata, dict) else {}
        tool_call_id = metadata_dict.get("tool_call_id")
        tool_call = metadata_dict.get("tool_call")
        hook_args = (
            dict(tool_call.get("args") or {})
            if isinstance(tool_call, dict) and isinstance(tool_call.get("args"), dict)
            else validated_args
        )
        object.__setattr__(self, "_config", runtime_config)
        object.__setattr__(
            self,
            "_tool_call_id",
            tool_call_id if isinstance(tool_call_id, str) else None,
        )
        hook_ctx = HookContext(
            tool_name=self.name,
            access_level=self.access_level,
            args=hook_args,
            state=self.runtime_state,
            config=runtime_config,
            tool_call_id=self.tool_call_id,
        )

        for hook in self._pre_hooks:
            hook_result = await hook(hook_ctx)
            if not hook_result.proceed:
                from langgraph.types import interrupt

                resume_value = interrupt(
                    await self._finalize_interrupt_payload(
                        hook_result.interrupt_payload,
                        args=validated_args,
                    )
                )
                if (
                    isinstance(hook_result.interrupt_payload, dict)
                    and hook_result.interrupt_payload.get("type") == "tool_approval"
                    and isinstance(resume_value, dict)
                    and resume_value.get("approved") is False
                ):
                    return json.dumps(
                        {
                            "error": "工具调用已被用户拒绝",
                            "approval_id": resume_value.get("approval_id"),
                            "tool_name": self.name,
                        },
                        ensure_ascii=False,
                    )

        try:
            execute = getattr(self, "_execute", None)
            if not callable(execute):
                raise NotImplementedError("AgentTool subclasses must define _execute")
            output = await cast(Callable[..., Awaitable[str]], execute)(**validated_args)
        except ToolExecutionError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
        except Exception as e:
            if "GraphInterrupt" in type(e).__name__:
                raise
            return json.dumps({"error": f"工具执行异常: {e}"}, ensure_ascii=False)

        hook_ctx.output = output
        for hook in self._post_hooks:
            hook_result = await hook(hook_ctx)
            if hook_result.output is not None:
                output = hook_result.output
                hook_ctx.output = output

        return output

    def _run(self, *args: Any, **kwargs: Any) -> str:
        raise NotImplementedError("Use ainvoke")
