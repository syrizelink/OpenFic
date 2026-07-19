"""ReAct subgraph factory.

Provides `create_react_agent` which builds an isolated ReAct (Reason + Act)
loop as a compiled LangGraph StateGraph. Each agent in the system uses this
factory to get its own loop instance.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Annotated, Any, Literal, Optional, TypedDict, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.tool import ToolCall
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph._internal._constants import CONF, CONFIG_KEY_RUNTIME
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.types import ReactAgentConfig
from app.agent_runtime.context import build_context, build_context_parts
from app.agent_runtime.context.processors.filter import filter_tool_result_metadata_content
from app.agent_runtime.context.helpers import compile_canonical_mentions
from app.agent_runtime.context.compaction.config import AUTO_TRIGGER_RATIO
from app.agent_runtime.context.compaction.service import CompactionError, compact_window
from app.agent_runtime.context.compaction.tokens import count_context_tokens
from app.agent_runtime.context.compaction.window import (
    CompactionNoWindowError,
    select_compaction_window,
)
from app.agent_runtime.context.processors.to_langchain import to_langchain_messages
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.persistence import compaction_repo
from app.agent_runtime.tool_call_recovery import (
    build_malformed_tool_call_error,
    is_malformed_tool_call,
    recover_message_tool_calls,
)

if TYPE_CHECKING:
    from app.audit import LLMCallAudit
    from app.agent_runtime.graph.state import AgentRuntimeState


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def _add_messages(left: list[BaseMessage], right: list[BaseMessage]) -> list[BaseMessage]:
    """Simple message list reducer — appends new messages."""
    return left + right


class ReactState(TypedDict):
    messages: Annotated[list[BaseMessage], _add_messages]
    iteration_count: int
    is_done: bool
    final_output: Any
    tool_call_cursor: int


# ---------------------------------------------------------------------------
# Module-level helper (exposed for mocking in tests)
# ---------------------------------------------------------------------------

async def _invoke_model(model: Any, messages: list[BaseMessage]) -> AIMessage:
    """Stream the LLM response and retain the first chunk latency for auditing."""
    start_time = time.perf_counter()
    first_token_ms: int | None = None
    response: AIMessage | None = None

    async for chunk in model.astream(messages):
        if first_token_ms is None:
            first_token_ms = int((time.perf_counter() - start_time) * 1000)
        response = chunk if response is None else response + chunk

    if response is None:
        raise ValueError("LLM流式调用未返回响应")

    object.__setattr__(response, "_openfic_first_token_ms", first_token_ms)
    return response


RetryEventSink = Callable[[dict[str, Any]], Awaitable[None]]

LLM_RETRY_POLICY = RetryPolicy(
    max_attempts=5,
    initial_interval=1.0,
    backoff_factor=2.0,
)


def _get_configurable(config: RunnableConfig | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    configurable = config.get(CONF)
    return configurable if isinstance(configurable, dict) else {}


def _get_runtime(config: RunnableConfig | None) -> Runtime[Any] | None:
    runtime = _get_configurable(config).get(CONFIG_KEY_RUNTIME)
    return runtime if isinstance(runtime, Runtime) else None


def _get_node_attempt(config: RunnableConfig | None) -> int:
    runtime = _get_runtime(config)
    execution_info = getattr(runtime, "execution_info", None) if runtime is not None else None
    attempt = getattr(execution_info, "node_attempt", None)
    return attempt if isinstance(attempt, int) and attempt > 0 else 1


def _get_retry_event_sink(config: RunnableConfig | None) -> RetryEventSink | None:
    value = _get_configurable(config).get("retry_event_sink")
    return value if callable(value) else None


def _should_retry_on(policy: RetryPolicy, exc: Exception) -> bool:
    retry_on = policy.retry_on
    if isinstance(retry_on, type):
        return isinstance(exc, retry_on)
    if isinstance(retry_on, Sequence):
        return any(isinstance(exc, cast(type[BaseException], exc_type)) for exc_type in retry_on)
    if callable(retry_on):
        return bool(retry_on(exc))
    return False


async def _emit_retry_event(
    config: RunnableConfig | None,
    *,
    session_id: str | None,
    node: str,
    attempt: int,
    max_attempts: int,
    exc: Exception,
) -> None:
    sink = _get_retry_event_sink(config)
    if sink is None or not session_id:
        return
    try:
        await sink({
            "session_id": session_id,
            "node": node,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
        })
    except Exception:
        return


def _extract_usage(message: AIMessage) -> dict[str, Any] | None:
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict) and usage:
        return dict(usage)
    if usage is not None and hasattr(usage, "items"):
        usage_dict = dict(usage)
        if usage_dict:
            return usage_dict

    response_metadata = getattr(message, "response_metadata", None)
    if isinstance(response_metadata, dict):
        metadata_usage = response_metadata.get("usage") or response_metadata.get(
            "token_usage"
        )
        if isinstance(metadata_usage, dict) and metadata_usage:
            return dict(metadata_usage)
        if metadata_usage is not None and hasattr(metadata_usage, "items"):
            usage_dict = dict(metadata_usage)
            if usage_dict:
                return usage_dict
    return None


def _error_status_code(exc: BaseException) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code if isinstance(status_code, int) else None


def _record_audit_error(audit: LLMCallAudit, exc: BaseException) -> None:
    audit.record_error(
        error_type=exc.__class__.__name__,
        error_message=str(exc),
        error_status_code=_error_status_code(exc),
    )


def _tool_result_payload(value: Any) -> tuple[dict[str, Any], bool]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"output": value}, True
        if isinstance(parsed, dict):
            return parsed, "error" not in parsed
        return {"output": parsed}, True
    if isinstance(value, Mapping):
        payload = dict(value)
        return payload, "error" not in payload
    return {"output": value}, True


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _emit_auto_compaction_error(
    event_sink: Callable[[str, dict[str, Any]], Awaitable[None] | None] | None,
    *,
    state: Mapping[str, Any],
    error: CompactionError,
) -> None:
    if event_sink is None:
        return
    try:
        result = event_sink(
            "agent:compaction_error",
            {
                "session_id": str(state.get("session_id") or ""),
                "task_id": str(state.get("task_id") or ""),
                "trigger": "auto",
                "code": error.code,
                "message": error.message,
            },
        )
        if inspect.isawaitable(result):
            await result
    except Exception:
        return


async def maybe_auto_compact(
    *,
    state: Mapping[str, Any],
    agent_name: str,
    parts: list[ContextMessage],
    db_session: Any,
    event_sink: Callable[[str, dict[str, Any]], Awaitable[None] | None] | None,
    usage_sink: Callable[[dict[str, Any]], Awaitable[None] | None] | None,
    model_config: Mapping[str, Any] | None = None,
) -> bool:
    del agent_name
    persisted_model_config = state.get("model_config")
    max_context_tokens = 0
    if isinstance(persisted_model_config, Mapping):
        raw_max_context_tokens = persisted_model_config.get("max_context_tokens")
        if isinstance(raw_max_context_tokens, int):
            max_context_tokens = raw_max_context_tokens
    if max_context_tokens <= 0:
        return False

    threshold = int(max_context_tokens * AUTO_TRIGGER_RATIO)
    if count_context_tokens(parts) < threshold:
        return False

    error_event_emitted = False

    async def tracked_event_sink(name: str, payload: dict[str, Any]) -> None:
        nonlocal error_event_emitted
        if name == "agent:compaction_error":
            error_event_emitted = True
        if event_sink is None:
            return
        result = event_sink(name, payload)
        if inspect.isawaitable(result):
            await result

    async def emit_error_once(error: CompactionError) -> None:
        nonlocal error_event_emitted
        if error_event_emitted:
            return
        error_event_emitted = True
        await _emit_auto_compaction_error(event_sink, state=state, error=error)

    history = [
        part for part in parts if (part.metadata or {}).get("part") == "history"
    ]
    try:
        compactions = await compaction_repo.list_by_session(
            db_session,
            str(state.get("session_id") or ""),
        )
    except Exception as exc:
        error = CompactionError("compaction_load_failed", "压缩状态加载失败，当前请求已中止")
        await emit_error_once(error)
        raise error from exc

    try:
        window = select_compaction_window(
            history,
            compactions,
            max_context_tokens,
        )
    except CompactionNoWindowError as exc:
        error = CompactionError("no_compactable_window", "没有可压缩的上下文窗口")
        await emit_error_once(error)
        raise error from exc
    except Exception as exc:
        error = CompactionError("compaction_window_failed", "压缩窗口选择失败，当前请求已中止")
        await emit_error_once(error)
        raise error from exc

    try:
        await compact_window(
            db_session,
            state=dict(state),
            window=window,
            trigger="auto",
            event_sink=tracked_event_sink if event_sink is not None else None,
            usage_sink=usage_sink,
            model_config=model_config,
        )
    except CompactionError as exc:
        await emit_error_once(exc)
        raise
    except Exception as exc:
        error = CompactionError("llm_error", "压缩失败，当前请求已中止")
        await emit_error_once(error)
        raise error from exc
    return True


async def _close_maybe(session: Any) -> None:
    close = getattr(session, "close", None)
    if callable(close):
        await _maybe_await(close())


async def _isolate_dispatch_config(
    config: RunnableConfig | None,
) -> tuple[RunnableConfig | None, Any | None]:
    if not isinstance(config, dict):
        return config, None
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return config, None
    session_factory = configurable.get("session_factory")
    if not callable(session_factory):
        return config, None

    session = await _maybe_await(session_factory())
    isolated = cast(RunnableConfig, dict(config))
    isolated_configurable = dict(configurable)
    isolated_configurable["db_session"] = session
    isolated["configurable"] = isolated_configurable
    return isolated, session


async def _isolate_tool_config(
    config: RunnableConfig | None,
) -> tuple[RunnableConfig | None, Any | None]:
    if not isinstance(config, dict):
        return config, None
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return config, None
    current_session = configurable.get("db_session")
    if not isinstance(current_session, AsyncSession):
        return config, None

    from app.storage.database import create_session

    session = await create_session()
    isolated = cast(RunnableConfig, dict(config))
    isolated_configurable = dict(configurable)
    isolated_configurable["db_session"] = session
    isolated["configurable"] = isolated_configurable
    return isolated, session


def _clone_agent_tool_for_dispatch(tool_instance: BaseTool) -> BaseTool:
    if not all(
        hasattr(tool_instance, attr)
        for attr in ("_state", "_pre_hooks", "_post_hooks")
    ):
        return tool_instance
    try:
        return tool_instance.__class__(
            _state=getattr(tool_instance, "_state", {}) or {},
            _pre_hooks=list(getattr(tool_instance, "_pre_hooks", []) or []),
            _post_hooks=list(getattr(tool_instance, "_post_hooks", []) or []),
        )
    except TypeError:
        return tool_instance


async def _invoke_tool(
    tool_instance: BaseTool,
    tool_args: dict[str, Any],
    tool_call: Mapping[str, Any] | None = None,
    config: RunnableConfig | None = None,
) -> Any:
    func = getattr(tool_instance, "func", None)
    if func is not None and getattr(
        tool_instance, "coroutine", None
    ) is None:
        return func(**tool_args)
    tool_config: RunnableConfig | None = config
    if tool_call is not None:
        tool_config_dict = dict(config or {})
        raw_metadata = tool_config_dict.get("metadata")
        metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
        metadata.update(
            {
                "tool_call_id": tool_call.get("id"),
                "tool_call": tool_call,
            }
        )
        tool_config_dict["metadata"] = metadata
        tool_config = cast(RunnableConfig, tool_config_dict)
    return await tool_instance.ainvoke(tool_args, config=tool_config)


def _to_history_dict(m: BaseMessage) -> dict:
    """把 LangChain BaseMessage 反向转成 build_context 期望的 history dict。"""
    # 用 isinstance 判断而非 m.type 字符串：流式累加产生的 *Chunk 子类
    # （如 AIMessageChunk）的 .type 是类名（"AIMessageChunk"）而非 "ai"，
    # 会导致 role 映射失败。
    if isinstance(m, ToolMessage):
        role = "tool"
    elif isinstance(m, AIMessage):
        role = "assistant"
    elif isinstance(m, HumanMessage):
        role = "user"
    elif isinstance(m, SystemMessage):
        role = "system"
    else:
        role = m.type
    response_metadata = getattr(m, "response_metadata", None)
    response_metadata = response_metadata if isinstance(response_metadata, dict) else {}
    metadata: dict[str, Any] = {"part": "history"}
    seq = response_metadata.get("openfic_seq")
    if type(seq) is int:
        metadata["seq"] = seq
    tool_name = response_metadata.get("openfic_tool_name")
    if isinstance(tool_name, str) and tool_name:
        metadata["tool_name"] = tool_name
    out: dict = {
        "role": role,
        "content": m.content if isinstance(m.content, str) else str(m.content),
        "metadata": metadata,
    }
    if isinstance(m, AIMessage) and m.tool_calls:
        out["tool_calls"] = list(m.tool_calls)
    if isinstance(m, AIMessage):
        additional_kwargs = getattr(m, "additional_kwargs", None)
        if isinstance(additional_kwargs, dict) and additional_kwargs:
            out["additional_kwargs"] = dict(additional_kwargs)
        else:
            reasoning_content = getattr(m, "reasoning_content", None)
            if isinstance(reasoning_content, str) and reasoning_content:
                out["additional_kwargs"] = {"reasoning_content": reasoning_content}
            else:
                if isinstance(response_metadata, dict):
                    for key in ("reasoning_content", "reasoning"):
                        value = response_metadata.get(key)
                        if isinstance(value, str) and value:
                            out["additional_kwargs"] = {"reasoning_content": value}
                            break
    if isinstance(m, ToolMessage):
        out["tool_call_id"] = m.tool_call_id
        if isinstance(tool_name, str) and tool_name:
            out["name"] = tool_name
        else:
            message_name = getattr(m, "name", None)
            if isinstance(message_name, str) and message_name:
                out["name"] = message_name
    return out


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_react_agent(
    config: ReactAgentConfig,
    model: Any | None = None,
    inject_queue: asyncio.Queue | None = None,
    checkpointer: Any | None = None,
):
    """Create and compile a ReAct subgraph from the given config.

    Parameters
    ----------
    config : ReactAgentConfig
        Agent configuration including tools, termination condition, etc.
    model : BaseChatModel | None
        The LLM to use. If None, a placeholder is used (tests mock _invoke_model).
    inject_queue : asyncio.Queue | None
        Optional queue for injecting user messages mid-execution.

    Returns
    -------
    CompiledStateGraph
        A compiled LangGraph ready for `ainvoke`.
    """

    react_config = config  # 重命名以避免与 LangGraph node 的 config 参数冲突
    tools = react_config.tools
    tool_map: dict[str, BaseTool] = {t.name: t for t in tools}
    termination = react_config.termination
    max_iterations = react_config.max_iterations

    # Bind tools to model if provided
    bound_model = model.bind_tools(tools) if model else None
    active_audit: LLMCallAudit | None = None

    async def _finish_active_audit(status: str = "success") -> None:
        nonlocal active_audit
        if active_audit is None:
            return
        audit = active_audit
        active_audit = None
        await audit.finish(status=status)

    async def _start_audit(
        configurable: dict[str, Any],
        messages: list[BaseMessage],
    ) -> LLMCallAudit | None:
        audit_context = configurable.get("audit_context")
        if audit_context is None:
            return None
        runtime_state = configurable.get("runtime_state") or {}
        model_cfg = runtime_state.get("model_config") if isinstance(runtime_state, dict) else {}
        if not isinstance(model_cfg, dict):
            model_cfg = {}

        audit = audit_context.llm_call(
            operation=react_config.name,
            model_id=str(model_cfg.get("model_id") or ""),
            model_provider=model_cfg.get("provider_type"),
            model_name=model_cfg.get("model_id"),
            request_messages=messages,
            tools=tools,
        )
        await audit.__aenter__()
        return audit

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    async def llm_call(state: ReactState, config: Optional[RunnableConfig] = None) -> dict:
        """Call the LLM with bound tools."""
        nonlocal active_audit
        configurable = cast(
            dict[str, Any],
            (config or {}).get("configurable", {}) if config else {},
        )
        runtime_state = configurable.get("runtime_state")
        db_session = configurable.get("db_session")
        inject_message_consumed_sink = configurable.get("inject_message_consumed_sink")
        if not callable(inject_message_consumed_sink):
            inject_message_consumed_sink = None
        agent_event_sink = configurable.get("agent_event_sink")
        if not callable(agent_event_sink):
            agent_event_sink = None
        compaction_usage_sink = configurable.get("compaction_usage_sink")
        if not callable(compaction_usage_sink):
            compaction_usage_sink = None
        runtime_model_config = configurable.get("model_config")
        if not isinstance(runtime_model_config, Mapping):
            runtime_model_config = None
        drained_injected_user_message = False
        context_parts: list[ContextMessage] | None = None
        effective_runtime_state: Mapping[str, Any] | None = None

        if isinstance(runtime_state, Mapping) and db_session is not None:
            node_messages = [_to_history_dict(m) for m in state["messages"]]
            runtime_context = configurable.get("runtime_context")
            effective_runtime_state = cast(
                Mapping[str, Any],
                {**runtime_state, **runtime_context}
                if isinstance(runtime_context, Mapping)
                else runtime_state,
            )
            model_config = effective_runtime_state.get("model_config")
            if (
                isinstance(model_config, Mapping)
                and model_config.get("max_context_tokens") is not None
            ):
                context_parts = await build_context_parts(
                    state=cast("AgentRuntimeState", effective_runtime_state),
                    agent_name=react_config.name,
                    node_messages=node_messages,
                    db_session=db_session,
                )
                messages: list[BaseMessage] = []
            else:
                messages = await build_context(
                    state=cast("AgentRuntimeState", effective_runtime_state),
                    agent_name=react_config.name,
                    node_messages=node_messages,
                    db_session=db_session,
                )
        else:
            messages = [
                ToolMessage(
                    content=(
                        filter_tool_result_metadata_content(message.content)
                        if isinstance(message.content, str)
                        else message.content
                    ),
                    tool_call_id=message.tool_call_id,
                    name=message.name,
                )
                if isinstance(message, ToolMessage)
                else message
                for message in state["messages"]
            ]

        transient_parts: list[ContextMessage] = []
        transient_messages: list[BaseMessage] = []

        # Drain inject_queue for user messages
        if inject_queue is not None:
            while not inject_queue.empty():
                try:
                    item = inject_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if isinstance(item, tuple):
                    message_id, role, content = item
                else:
                    message_id = None
                    role, content = "user", item
                if role == "system":
                    transient_parts.append(
                        ContextMessage(
                            role="system",
                            content=content,
                            metadata={"part": "runtime"},
                        )
                    )
                    transient_messages.append(SystemMessage(content=content))
                else:
                    should_inject = True
                    if (
                        isinstance(message_id, str)
                        and message_id
                        and inject_message_consumed_sink is not None
                    ):
                        consumed = inject_message_consumed_sink(message_id)
                        if inspect.isawaitable(consumed):
                            consumed = await consumed
                        should_inject = consumed is not False
                    if should_inject:
                        compiled_content = content
                        if (
                            db_session is not None
                            and isinstance(content, str)
                            and "<of-mention" in content
                        ):
                            compiled_content = await compile_canonical_mentions(content, db_session)
                        drained_injected_user_message = True
                        transient_parts.append(
                            ContextMessage(
                                role="user",
                                content=compiled_content,
                                metadata={"part": "runtime"},
                            )
                        )
                        transient_messages.append(HumanMessage(content=compiled_content))

        if (
            termination.mode == "tool_success"
            and termination.tool_name
            and state["iteration_count"] > 0
        ):
            last_state_message = state["messages"][-1] if state["messages"] else None
            if isinstance(last_state_message, AIMessage) and not last_state_message.tool_calls:
                termination_hint = (
                    f"Call the `{termination.tool_name}` tool to finish this step. "
                    "Do not answer in plain text."
                )
                transient_parts.append(
                    ContextMessage(
                        role="user",
                        content=termination_hint,
                        metadata={"part": "runtime"},
                    )
                )
                transient_messages.append(HumanMessage(content=termination_hint))

        if context_parts is not None and effective_runtime_state is not None:
            runtime_db_session = cast("AsyncSession", db_session)
            candidate_parts = [*context_parts, *transient_parts]
            if await maybe_auto_compact(
                state=effective_runtime_state,
                agent_name=react_config.name,
                parts=candidate_parts,
                db_session=runtime_db_session,
                event_sink=agent_event_sink,
                usage_sink=compaction_usage_sink,
                model_config=runtime_model_config,
            ):
                context_parts = await build_context_parts(
                    state=cast("AgentRuntimeState", effective_runtime_state),
                    agent_name=react_config.name,
                    node_messages=node_messages,
                    db_session=runtime_db_session,
                )
                candidate_parts = [*context_parts, *transient_parts]
            messages = to_langchain_messages(candidate_parts)
        else:
            messages.extend(transient_messages)

        audit = await _start_audit(configurable, messages)
        active_audit = audit
        try:
            response = await _invoke_model(bound_model or model, messages)
        except Exception as exc:
            if audit is not None:
                _record_audit_error(audit, exc)
                await _finish_active_audit(status="error")
            session_id = runtime_state.get("session_id") if isinstance(runtime_state, Mapping) else None
            current_attempt = _get_node_attempt(config)
            if (
                current_attempt < LLM_RETRY_POLICY.max_attempts
                and _should_retry_on(LLM_RETRY_POLICY, exc)
            ):
                await _emit_retry_event(
                    config,
                    session_id=session_id if isinstance(session_id, str) else None,
                    node=react_config.name,
                    attempt=current_attempt + 1,
                    max_attempts=LLM_RETRY_POLICY.max_attempts,
                    exc=exc,
                )
            raise

        recovered_tool_calls = cast(
            list[ToolCall],
            recover_message_tool_calls(
                response,
                id_seed=f"{react_config.name}:{state['iteration_count']}",
            ),
        )
        if (
            isinstance(getattr(response, "tool_calls", None), list)
            or isinstance(getattr(response, "invalid_tool_calls", None), list)
        ):
            response.tool_calls = recovered_tool_calls

        if audit is not None:
            audit.record_response(
                content=response.content if isinstance(response.content, str) else str(response.content),
                tool_calls=cast(list[dict[str, Any]], response.tool_calls or []),
                usage=_extract_usage(response),
                first_token_ms=getattr(response, "_openfic_first_token_ms", None),
            )
            if not response.tool_calls:
                await _finish_active_audit()

        update: dict[str, Any] = {
            "messages": [response],
            "iteration_count": state["iteration_count"] + 1,
            "tool_call_cursor": 0,
        }
        if drained_injected_user_message:
            update["is_done"] = False
            update["final_output"] = None
        return update

    async def tools_exec(state: ReactState, config: Optional[RunnableConfig] = None) -> dict:
        """Execute tool calls from the last AI message."""
        last_message = next(
            (
                message
                for message in reversed(state["messages"])
                if isinstance(message, AIMessage) and message.tool_calls
            ),
            None,
        )
        if last_message is None:
            return {"messages": [], "tool_call_cursor": 0}
        tool_calls: list[ToolCall] = list(last_message.tool_calls)
        cursor = state.get("tool_call_cursor", 0)
        if cursor >= len(tool_calls):
            return {"messages": [], "tool_call_cursor": 0}
        new_messages: list[BaseMessage] = []
        is_done = False
        final_output = None
        audit_finished = False
        dispatch_tool = tool_map.get("dispatch_subagent")
        dispatch_state = getattr(dispatch_tool, "_state", None)
        if isinstance(dispatch_state, dict):
            dispatch_state["_dispatch_subagent_count"] = 0

        async def execute_one(tc: ToolCall) -> dict[str, Any]:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_id = tc["id"]
            started_at = time.perf_counter()
            tool_result_payload: dict[str, Any] = {}
            tool_success = False
            message: ToolMessage
            if is_malformed_tool_call(tc):
                tool_result_payload = build_malformed_tool_call_error(tc)
                message = ToolMessage(
                    content=json.dumps(tool_result_payload, ensure_ascii=False),
                    tool_call_id=tool_id,
                    name=tool_name,
                )
                return {
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "message": message,
                    "payload": tool_result_payload,
                    "success": False,
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                }

            tool_instance = tool_map.get(tool_name)
            if tool_instance:
                result = await _invoke_tool(tool_instance, tool_args, tc, config)
                tool_result_payload, tool_success = _tool_result_payload(result)
                message = ToolMessage(content=str(result), tool_call_id=tool_id)
            else:
                tool_result_payload = {"error": f"tool '{tool_name}' not found."}
                message = ToolMessage(
                    content=f"Error: tool '{tool_name}' not found.", tool_call_id=tool_id
                )
            return {
                "tool_name": tool_name,
                "tool_args": tool_args,
                "message": message,
                "payload": tool_result_payload,
                "success": tool_success,
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
            }

        async def build_pending_previews(tool_calls: list[ToolCall]) -> list[dict[str, Any]]:
            previews: list[dict[str, Any]] = []
            for tool_call in tool_calls:
                tool_instance = tool_map.get(tool_call["name"])
                if not isinstance(tool_instance, BaseTool):
                    continue
                preview_builder = getattr(tool_instance, "build_interrupt_preview", None)
                if not callable(preview_builder):
                    continue
                tool_instance = _clone_agent_tool_for_dispatch(tool_instance)
                invoke_config, isolated_session = await _isolate_tool_config(config)
                try:
                    object.__setattr__(tool_instance, "_config", invoke_config)
                    preview_builder = getattr(tool_instance, "build_interrupt_preview", None)
                    preview = (
                        await preview_builder(tool_call["args"])
                        if callable(preview_builder)
                        else None
                    )
                finally:
                    if isolated_session is not None:
                        await _close_maybe(isolated_session)
                if isinstance(preview, dict):
                    previews.append(
                        {
                            "tool_call_id": tool_call["id"],
                            "tool_name": tool_call["name"],
                            "args": tool_call["args"],
                            "preview": preview,
                        }
                    )
            return previews

        async def record_outcome(outcome: dict[str, Any]) -> None:
            nonlocal is_done, final_output
            new_messages.append(outcome["message"])
            tool_name = outcome["tool_name"]
            tool_success = bool(outcome["success"])
            if (
                termination.mode == "tool_success"
                and termination.tool_name == tool_name
                and tool_success
            ):
                is_done = True
                final_output = outcome["tool_args"]
            if active_audit is not None:
                active_audit.record_tool_call(
                    tool_name=tool_name,
                    tool_args=outcome["tool_args"],
                    tool_result=outcome["payload"],
                    success=tool_success,
                    latency_ms=outcome["latency_ms"],
                )

        try:
            try:
                await record_outcome(await execute_one(tool_calls[cursor]))
            except GraphInterrupt as interrupt:
                if cursor == 0:
                    previews = await build_pending_previews(tool_calls)
                    if previews and interrupt.args and interrupt.args[0]:
                        interrupt_value = interrupt.args[0][0].value
                        if isinstance(interrupt_value, dict):
                            interrupt_value["tool_result_previews"] = previews
                raise

            update: dict[str, Any] = {
                "messages": new_messages,
                "tool_call_cursor": cursor + 1,
            }
            if is_done:
                update["is_done"] = True
                update["final_output"] = final_output
            await _finish_active_audit()
            audit_finished = True
            return update
        except GraphInterrupt:
            raise
        except Exception as exc:
            if active_audit is not None:
                _record_audit_error(active_audit, exc)
            await _finish_active_audit(status="error")
            audit_finished = True
            raise
        finally:
            if not audit_finished:
                await _finish_active_audit()

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    async def route_after_llm(state: ReactState) -> Literal["llm_call", "tools_exec", "__end__"]:
        """Route after LLM call."""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools_exec"

        if inject_queue is not None and not inject_queue.empty():
            return "llm_call"

        if state.get("is_done"):
            return "__end__"

        if termination.mode == "no_tool_call":
            return "__end__"

        if state["iteration_count"] >= max_iterations:
            return "__end__"

        return "llm_call"

    async def route_after_tools(state: ReactState) -> Literal["tools_exec", "llm_call", "__end__"]:
        last_message = next(
            (
                message
                for message in reversed(state["messages"])
                if isinstance(message, AIMessage) and message.tool_calls
            ),
            None,
        )
        if (
            last_message is not None
            and state.get("tool_call_cursor", 0) < len(last_message.tool_calls)
        ):
            return "tools_exec"
        if inject_queue is not None and not inject_queue.empty():
            return "llm_call"
        if state.get("is_done"):
            return "__end__"
        if state["iteration_count"] >= max_iterations:
            return "__end__"
        return "llm_call"

    # ------------------------------------------------------------------
    # Build graph
    # ------------------------------------------------------------------

    graph = StateGraph(cast(Any, ReactState))

    graph.add_node(
        "llm_call",
        llm_call,
        retry_policy=LLM_RETRY_POLICY,
    )
    graph.add_node("tools_exec", tools_exec)

    graph.add_edge(START, "llm_call")
    graph.add_conditional_edges(
        "llm_call",
        route_after_llm,
        {"llm_call": "llm_call", "tools_exec": "tools_exec", "__end__": END},
    )
    graph.add_conditional_edges(
        "tools_exec",
        route_after_tools,
        {"tools_exec": "tools_exec", "llm_call": "llm_call", "__end__": END},
    )

    compiled = graph.compile(checkpointer=checkpointer)

    # Wrap ainvoke to normalize completion state.
    _original_ainvoke = compiled.ainvoke

    async def _wrapped_ainvoke(*args, **kwargs):
        result = await _original_ainvoke(*args, **kwargs)
        if "__interrupt__" in result:
            return result
        if termination.mode == "tool_success" and not result.get("is_done"):
            expected_tool = termination.tool_name or "the configured termination tool"
            raise RuntimeError(
                f"Agent '{react_config.name}' ended before calling '{expected_tool}'."
            )
        if not result.get("is_done"):
            result["is_done"] = True
        return result

    cast(Any, compiled).ainvoke = _wrapped_ainvoke

    return compiled
