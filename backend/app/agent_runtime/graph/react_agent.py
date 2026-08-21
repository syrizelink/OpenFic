"""ReAct subgraph factory.

Provides `create_react_agent` which builds an isolated ReAct (Reason + Act)
loop as a compiled LangGraph StateGraph. Each agent in the system uses this
factory to get its own loop instance.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import TYPE_CHECKING, Annotated, Any, Literal, Optional, TypedDict, cast

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.tool import ToolCall
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph._internal._constants import CONF
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.types import Overwrite, RetryPolicy, Send
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.content_blocks import extract_text_content
from app.agent_runtime.attachments import build_image_content_blocks
from app.agent_runtime.types import ReactAgentConfig
from app.agent_runtime.context import build_context, build_context_parts
from app.agent_runtime.context.processors.filter import (
    filter_tool_result_metadata_content,
)
from app.agent_runtime.context.helpers import (
    compile_canonical_mentions,
    extract_referenced_skill_ids,
)
from app.agent_runtime.context.compaction.config import AUTO_TRIGGER_RATIO
from app.agent_runtime.context.compaction.service import CompactionError, compact_window
from app.agent_runtime.context.compaction.tokens import count_context_tokens
from app.agent_runtime.context.compaction.window import (
    CompactionNoWindowError,
    select_compaction_window,
)
from app.agent_runtime.context.processors.to_langchain import to_langchain_messages
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.graph.llm_invoke import (
    EmptyResponseError,
    RetryEventSink,
    _TimedStream,
    invoke_model_with_retry,
    load_llm_invoke_settings,
)
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


def _add_messages(
    left: list[BaseMessage], right: list[BaseMessage]
) -> list[BaseMessage]:
    """Simple message list reducer — appends new messages."""
    return left + right


class ReactState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], _add_messages]
    iteration_count: int
    is_done: bool
    final_output: Any
    tool_index: int
    tool_call: ToolCall
    tool_batch_offset: int
    tool_dispatch_denied: bool
    tool_phase: Literal["prepare", "execute"]
    tool_outcomes: Annotated[list[dict[str, Any]], _add_messages]
    tool_prepared_outcomes: Annotated[list[dict[str, Any]], _add_messages]


# ---------------------------------------------------------------------------
# Module-level helper (exposed for mocking in tests)
# ---------------------------------------------------------------------------


async def _invoke_model(
    model: Any,
    messages: list[BaseMessage],
    *,
    chunk_timeout: float | None = None,
) -> AIMessage:
    """Stream the LLM response and normalize it for checkpoint persistence."""
    start_time = time.perf_counter()
    first_token_ms: int | None = None
    response: AIMessage | None = None

    stream = _TimedStream(
        model.astream(messages),
        chunk_timeout=chunk_timeout,
    )
    async for chunk in stream:
        if first_token_ms is None:
            first_token_ms = int((time.perf_counter() - start_time) * 1000)
        response = chunk if response is None else response + chunk

    if response is None:
        raise EmptyResponseError("LLM流式调用未返回响应")

    normalized = AIMessage(
        content=extract_text_content(response.content),
        additional_kwargs=dict(response.additional_kwargs or {}),
        response_metadata=dict(response.response_metadata or {}),
        tool_calls=recover_message_tool_calls(response),
        usage_metadata=response.usage_metadata,
        id=response.id,
        name=response.name,
    )
    object.__setattr__(normalized, "_openfic_first_token_ms", first_token_ms)
    return normalized


# 节点级重试已禁用：超时与重试统一由模型调用层（invoke_model_with_retry）处理，
# 避免双层重试叠加。保留常量名以便测试禁用兜底重试。
LLM_RETRY_POLICY = RetryPolicy(max_attempts=1)
TOOL_BATCH_SIZE = 20


def _get_configurable(config: RunnableConfig | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    configurable = config.get(CONF)
    return configurable if isinstance(configurable, dict) else {}


def _get_retry_event_sink(config: RunnableConfig | None) -> RetryEventSink | None:
    value = _get_configurable(config).get("retry_event_sink")
    return value if callable(value) else None


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

    history = [part for part in parts if (part.metadata or {}).get("part") == "history"]
    try:
        compactions = await compaction_repo.list_by_session(
            db_session,
            str(state.get("session_id") or ""),
        )
    except Exception as exc:
        error = CompactionError(
            "compaction_load_failed", "压缩状态加载失败，当前请求已中止"
        )
        await emit_error_once(error)
        raise error from exc

    try:
        window = select_compaction_window(
            history,
            compactions,
            max_context_tokens,
        )
    except CompactionNoWindowError:
        return False
    except Exception as exc:
        error = CompactionError(
            "compaction_window_failed", "压缩窗口选择失败，当前请求已中止"
        )
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
        hasattr(tool_instance, attr) for attr in ("_state", "_pre_hooks", "_post_hooks")
    ):
        return tool_instance
    try:
        cloned = copy.copy(tool_instance)
        runtime_state = getattr(tool_instance, "runtime_state", None)
        pre_hooks = getattr(tool_instance, "pre_hooks", None)
        post_hooks = getattr(tool_instance, "post_hooks", None)
        if isinstance(runtime_state, dict):
            object.__setattr__(cloned, "runtime_state", dict(runtime_state))
        if isinstance(pre_hooks, list):
            object.__setattr__(cloned, "pre_hooks", list(pre_hooks))
        if isinstance(post_hooks, list):
            object.__setattr__(cloned, "post_hooks", list(post_hooks))
        object.__setattr__(cloned, "_config", None)
        object.__setattr__(cloned, "_tool_call_id", None)
        return cloned
    except Exception:
        pass
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
    if func is not None and getattr(tool_instance, "coroutine", None) is None:
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
        "content": extract_text_content(m.content),
        "metadata": metadata,
    }
    if isinstance(m, HumanMessage):
        additional_kwargs = getattr(m, "additional_kwargs", None)
        attachments = (
            additional_kwargs.get("openfic_attachments")
            if isinstance(additional_kwargs, dict)
            else None
        )
        if isinstance(attachments, list):
            out["additional_kwargs"] = {"openfic_attachments": attachments}
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


def _runtime_skill_ids(runtime_state: Mapping[str, Any]) -> tuple[str, ...]:
    values = runtime_state.get("referenced_skill_ids")
    return _merge_skill_ids(values)


def _merge_skill_ids(*groups: object) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        values = group if isinstance(group, (list, tuple, set)) else (group,)
        for value in values:
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if normalized and normalized not in merged:
                merged.append(normalized)
    return tuple(merged)


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

    def update_skill_tool_references(referenced_skill_ids: Iterable[str]) -> None:
        values = list(referenced_skill_ids)
        for tool in tools:
            runtime_state = getattr(tool, "runtime_state", None)
            if isinstance(runtime_state, dict):
                runtime_state["referenced_skill_ids"] = values

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
        model_cfg = (
            runtime_state.get("model_config") if isinstance(runtime_state, dict) else {}
        )
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

    async def llm_call(
        state: ReactState, config: Optional[RunnableConfig] = None
    ) -> dict:
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
        inject_message_attachments = configurable.get("inject_message_attachments")
        if not callable(inject_message_attachments):
            inject_message_attachments = None
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
        effective_runtime_state: dict[str, Any] | None = None
        injected_user_contents: list[str] = []

        if isinstance(runtime_state, Mapping) and db_session is not None:
            node_messages = [_to_history_dict(m) for m in state["messages"]]
            runtime_context = configurable.get("runtime_context")
            effective_runtime_state = dict(runtime_state)
            if isinstance(runtime_context, Mapping):
                effective_runtime_state.update(runtime_context)
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
                        if (
                            isinstance(content, str)
                            and "<of-skill" in content
                        ):
                            injected_user_contents.append(content)
                        compiled_content = content
                        if (
                            db_session is not None
                            and isinstance(content, str)
                            and ("<of-mention" in content or "<of-skill" in content)
                        ):
                            compiled_content = await compile_canonical_mentions(
                                content, db_session
                            )
                        drained_injected_user_message = True
                        attachment_metadata = (
                            inject_message_attachments(message_id)
                            if isinstance(message_id, str) and inject_message_attachments is not None
                            else []
                        )
                        attachments = await build_image_content_blocks(attachment_metadata)
                        transient_parts.append(
                            ContextMessage(
                                role="user",
                                content=compiled_content,
                                metadata={"part": "runtime"},
                                attachments=attachments,
                            )
                        )
                        transient_messages.extend(
                            to_langchain_messages(
                                [
                                    ContextMessage(
                                        role="user",
                                        content=compiled_content,
                                        attachments=attachments,
                                    )
                                ]
                            )
                        )

        if injected_user_contents and effective_runtime_state is not None:
            injected_skill_ids = extract_referenced_skill_ids(injected_user_contents)
            current_skill_ids = _runtime_skill_ids(effective_runtime_state)
            merged_skill_ids = _merge_skill_ids(current_skill_ids, injected_skill_ids)
            if merged_skill_ids != current_skill_ids:
                effective_runtime_state["referenced_skill_ids"] = list(merged_skill_ids)
                update_skill_tool_references(merged_skill_ids)
                if context_parts is not None:
                    context_parts = await build_context_parts(
                        state=cast("AgentRuntimeState", effective_runtime_state),
                        agent_name=react_config.name,
                        node_messages=node_messages,
                        db_session=cast("AsyncSession", db_session),
                    )
                else:
                    messages = await build_context(
                        state=cast("AgentRuntimeState", effective_runtime_state),
                        agent_name=react_config.name,
                        node_messages=node_messages,
                        db_session=cast("AsyncSession", db_session),
                    )

        if (
            termination.mode == "tool_success"
            and termination.tool_name
            and state["iteration_count"] > 0
        ):
            last_state_message = state["messages"][-1] if state["messages"] else None
            if (
                isinstance(last_state_message, AIMessage)
                and not last_state_message.tool_calls
            ):
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
            session_id = (
                runtime_state.get("session_id")
                if isinstance(runtime_state, Mapping)
                else None
            )
            response = await invoke_model_with_retry(
                bound_model or model,
                messages,
                invoke=_invoke_model,
                settings=load_llm_invoke_settings(),
                session_id=session_id if isinstance(session_id, str) else None,
                node=react_config.name,
                retry_event_sink=_get_retry_event_sink(config),
            )
        except Exception as exc:
            if audit is not None:
                _record_audit_error(audit, exc)
                await _finish_active_audit(status="error")
            raise

        recovered_tool_calls = cast(
            list[ToolCall],
            recover_message_tool_calls(
                response,
                id_seed=f"{react_config.name}:{state['iteration_count']}",
            ),
        )
        if isinstance(getattr(response, "tool_calls", None), list) or isinstance(
            getattr(response, "invalid_tool_calls", None), list
        ):
            response.tool_calls = recovered_tool_calls

        if audit is not None:
            audit.record_response(
                content=response.content
                if isinstance(response.content, str)
                else str(response.content),
                tool_calls=cast(list[dict[str, Any]], response.tool_calls or []),
                usage=_extract_usage(response),
                first_token_ms=getattr(response, "_openfic_first_token_ms", None),
            )
            if not response.tool_calls:
                await _finish_active_audit()

        update: dict[str, Any] = {
            "messages": [response],
            "iteration_count": state["iteration_count"] + 1,
            "tool_outcomes": Overwrite([]),
            "tool_prepared_outcomes": Overwrite([]),
            "tool_phase": "prepare",
        }
        if drained_injected_user_message:
            update["is_done"] = False
            update["final_output"] = None
        return update

    async def tool_exec(
        state: ReactState, config: Optional[RunnableConfig] = None
    ) -> dict:
        """Execute one tool call in an isolated fan-out branch."""
        tool_call = state.get("tool_call")
        if not isinstance(tool_call, dict):
            return {"tool_outcomes": []}

        tool_name = str(tool_call.get("name") or "")
        tool_args = tool_call.get("args")
        tool_args = tool_args if isinstance(tool_args, dict) else {}
        tool_id = str(tool_call.get("id") or "")
        tool_index = int(state.get("tool_index") or 0)
        started_at = time.perf_counter()
        phase = state.get("tool_phase") or "execute"
        source_outcomes = (
            state.get("tool_prepared_outcomes", [])
            if phase == "execute"
            else []
        )
        prepared_outcome = next(
            (
                outcome
                for outcome in source_outcomes
                if outcome.get("tool_call_id") == tool_id
            ),
            None,
        )

        def outcome_update(outcome: dict[str, Any]) -> dict[str, Any]:
            key = "tool_prepared_outcomes" if phase == "prepare" else "tool_outcomes"
            return {key: [outcome]}

        if state.get("tool_dispatch_denied"):
            payload = {
                "error": "dispatch_subagent allows at most 10 dispatches per PA turn"
            }
            result = json.dumps(payload, ensure_ascii=False)
            return outcome_update(
                {
                        "index": tool_index,
                        "tool_call_id": tool_id,
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "message": ToolMessage(
                            content=result,
                            tool_call_id=tool_id,
                            name=tool_name,
                        ),
                        "payload": payload,
                        "success": False,
                        "latency_ms": int((time.perf_counter() - started_at) * 1000),
                }
            )

        if is_malformed_tool_call(tool_call):
            payload = build_malformed_tool_call_error(tool_call)
            result = json.dumps(payload, ensure_ascii=False)
            return outcome_update(
                {
                        "index": tool_index,
                        "tool_call_id": tool_id,
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "message": ToolMessage(
                            content=result,
                            tool_call_id=tool_id,
                            name=tool_name,
                        ),
                        "payload": payload,
                        "success": False,
                        "latency_ms": int((time.perf_counter() - started_at) * 1000),
                }
            )

        tool_instance = tool_map.get(tool_name)
        if tool_instance is None:
            payload = {"error": f"tool '{tool_name}' not found."}
            result = f"Error: tool '{tool_name}' not found."
            return outcome_update(
                {
                        "index": tool_index,
                        "tool_call_id": tool_id,
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "message": ToolMessage(
                            content=result,
                            tool_call_id=tool_id,
                            name=tool_name,
                        ),
                        "payload": payload,
                        "success": False,
                        "latency_ms": int((time.perf_counter() - started_at) * 1000),
                }
            )

        if phase == "prepare" and not getattr(tool_instance, "_pre_hooks", []):
            payload = {"__openfic_prepared": True}
            result = json.dumps(payload)
            return outcome_update(
                {
                    "index": tool_index,
                    "tool_call_id": tool_id,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "message": ToolMessage(
                        content=result,
                        tool_call_id=tool_id,
                        name=tool_name,
                    ),
                    "payload": payload,
                    "success": True,
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                }
            )

        if (
            phase == "execute"
            and prepared_outcome is not None
            and (
                getattr(tool_instance, "execute_during_prepare", False)
                or not bool(prepared_outcome.get("success"))
            )
        ):
            if not bool(prepared_outcome.get("success")):
                tool_result_sink = _get_configurable(config).get("tool_result_sink")
                if callable(tool_result_sink):
                    rejected_payload = dict(prepared_outcome.get("payload") or {})
                    rejected_payload.update(
                        {
                            "type": "fail",
                            "success": False,
                            "reason": "tool_error",
                            "tool_call_id": tool_id,
                            "tool_name": tool_name,
                        }
                    )
                    await _maybe_await(
                        tool_result_sink(
                            {
                                "session_id": _get_configurable(config).get("session_id"),
                                "tool_call_id": tool_id,
                                "tool_name": tool_name,
                                "input": tool_args,
                                "output": rejected_payload,
                            }
                        )
                    )
            return {"tool_outcomes": [prepared_outcome]}

        tool_instance = _clone_agent_tool_for_dispatch(tool_instance)
        isolated_config, isolated_session = await _isolate_tool_config(config)
        try:
            invoke_config = dict(isolated_config or {})
            metadata = dict(invoke_config.get("metadata") or {})
            metadata["tool_call_id"] = tool_id
            metadata["tool_call"] = tool_call
            metadata["openfic_phase"] = phase
            if phase == "execute":
                metadata["openfic_skip_pre_hooks"] = True
            invoke_config["metadata"] = metadata
            if phase == "prepare" and not getattr(
                tool_instance, "emit_prepare_events", False
            ):
                if hasattr(tool_instance, "_pre_hooks"):
                    result = await tool_instance._arun(
                        config=cast(RunnableConfig, invoke_config),
                        **tool_args,
                    )
                else:
                    result = json.dumps({"__openfic_prepared": True})
            else:
                result = await _invoke_tool(
                    tool_instance,
                    tool_args,
                    tool_call,
                    cast(RunnableConfig, invoke_config),
                )
        except GraphInterrupt as interrupt:
            preview_builder = getattr(tool_instance, "build_interrupt_preview", None)
            if interrupt.args and interrupt.args[0]:
                interrupt_value = interrupt.args[0][0].value
                if isinstance(interrupt_value, dict):
                    interrupt_value.setdefault("tool_call_id", tool_id)
                    interrupt_value.setdefault("tool_name", tool_name)
                    interrupt_value.setdefault("args", tool_args)
                    interrupt_value.setdefault("tool_index", tool_index)
                    if callable(preview_builder):
                        preview = await preview_builder(tool_args)
                        if isinstance(preview, dict):
                            interrupt_value["tool_result_preview"] = preview
            await _finish_active_audit()
            raise
        except Exception as exc:
            if active_audit is not None:
                _record_audit_error(active_audit, exc)
            await _finish_active_audit(status="error")
            raise
        finally:
            if isolated_session is not None:
                await _close_maybe(isolated_session)

        payload, success = _tool_result_payload(result)
        if phase == "prepare" and not getattr(
            tool_instance, "execute_during_prepare", False
        ):
            if not success:
                prepared_payload = payload
                prepared_result = result
            else:
                prepared_payload = {"__openfic_prepared": True}
                prepared_result = json.dumps(prepared_payload)
            payload = prepared_payload
            result = prepared_result
        outcome = {
                    "index": tool_index,
                    "tool_call_id": tool_id,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "message": ToolMessage(
                        content=str(result),
                        tool_call_id=tool_id,
                        name=tool_name,
                    ),
                    "payload": payload,
                    "success": success,
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                }
        if phase == "prepare" and not success:
            return outcome_update(outcome)
        return outcome_update(outcome)

    async def tools_join(
        state: ReactState, _config: Optional[RunnableConfig] = None
    ) -> dict:
        """Join parallel tool results and restore model call order."""
        outcomes = sorted(
            state.get("tool_outcomes", []), key=lambda outcome: outcome["index"]
        )
        if state.get("tool_phase") == "prepare":
            return {
                "tool_outcomes": Overwrite([]),
                "tool_phase": "execute",
            }
        messages = [outcome["message"] for outcome in outcomes]
        is_done = False
        final_output = None
        for outcome in outcomes:
            tool_name = outcome["tool_name"]
            success = bool(outcome["success"])
            if (
                not is_done
                and termination.mode == "tool_success"
                and termination.tool_name == tool_name
                and success
            ):
                is_done = True
                final_output = outcome["tool_args"]
            if not is_done and tool_name == "ask_user" and outcome["payload"].get("status") == "user_skipped":
                is_done = True
                final_output = outcome["payload"]
            if active_audit is not None:
                active_audit.record_tool_call(
                    tool_name=tool_name,
                    tool_args=outcome["tool_args"],
                    tool_result=outcome["payload"],
                    success=success,
                    latency_ms=outcome["latency_ms"],
                )

        await _finish_active_audit()
        update: dict[str, Any] = {
            "messages": messages,
            "tool_outcomes": Overwrite([]),
            "tool_prepared_outcomes": Overwrite([]),
            "tool_phase": "prepare",
        }
        if is_done:
            update["is_done"] = True
            update["final_output"] = final_output
        return update

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    async def dispatch_tools(
        state: ReactState, config: Optional[RunnableConfig] = None
    ) -> dict:
        excess_outcomes: list[dict[str, Any]] = []
        error_message = (
            f"Agent 单轮最多调用 {TOOL_BATCH_SIZE} 个工具，"
            "超出上限的工具调用未执行"
        )
        for message in reversed(state["messages"]):
            if isinstance(message, AIMessage) and message.tool_calls:
                for offset, tool_call in enumerate(
                    message.tool_calls[TOOL_BATCH_SIZE:]
                ):
                    tool_name = str(tool_call.get("name") or "")
                    tool_id = str(tool_call.get("id") or "")
                    tool_args = tool_call.get("args")
                    tool_args = tool_args if isinstance(tool_args, dict) else {}
                    payload = {"error": error_message}
                    result = json.dumps(payload, ensure_ascii=False)
                    excess_outcomes.append(
                        {
                            "index": TOOL_BATCH_SIZE + offset,
                            "tool_call_id": tool_id,
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "message": ToolMessage(
                                content=result,
                                tool_call_id=tool_id,
                                name=tool_name,
                            ),
                            "payload": payload,
                            "success": False,
                            "latency_ms": 0,
                        }
                    )
                break
        if not excess_outcomes:
            return {}
        if state.get("tool_phase") == "execute":
            tool_result_sink = _get_configurable(config).get("tool_result_sink")
            if callable(tool_result_sink):
                for outcome in excess_outcomes:
                    output_payload = {
                        "type": "fail",
                        "success": False,
                        "reason": "tool_error",
                        "message": error_message,
                        "tool_call_id": outcome["tool_call_id"],
                        "tool_name": outcome["tool_name"],
                    }
                    result = tool_result_sink(
                        {
                            "session_id": _get_configurable(config).get("session_id"),
                            "tool_call_id": outcome["tool_call_id"],
                            "tool_name": outcome["tool_name"],
                            "input": outcome["tool_args"],
                            "output": output_payload,
                        }
                    )
                    if inspect.isawaitable(result):
                        await result
        return {"tool_outcomes": excess_outcomes}

    def route_tool_batch(state: ReactState) -> list[Send]:
        last_message = next(
            (
                message
                for message in reversed(state["messages"])
                if isinstance(message, AIMessage) and message.tool_calls
            ),
            None,
        )
        if last_message is None:
            return []
        dispatch_count = 0
        sends: list[Send] = []
        for slot in range(TOOL_BATCH_SIZE):
            index = slot
            tool_call = (
                last_message.tool_calls[index]
                if index < len(last_message.tool_calls)
                else None
            )
            denied = False
            if tool_call is not None and tool_call["name"] == "dispatch_subagent":
                denied = dispatch_count >= 10
                dispatch_count += 1
            sends.append(
                Send(
                    f"tool_exec_{slot}",
                    {
                        "tool_index": index,
                        "tool_call": tool_call,
                        "tool_dispatch_denied": denied,
                        "tool_phase": state.get("tool_phase", "prepare"),
                        "tool_prepared_outcomes": state.get(
                            "tool_prepared_outcomes", []
                        ),
                    },
                )
            )
        return sends

    async def route_after_llm(
        state: ReactState,
    ) -> Literal["dispatch_tools", "llm_call", "__end__"]:
        """Route after LLM call."""
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "dispatch_tools"

        if inject_queue is not None and not inject_queue.empty():
            return "llm_call"

        if state.get("is_done"):
            return "__end__"

        if termination.mode == "no_tool_call":
            return "__end__"

        if state["iteration_count"] >= max_iterations:
            return "__end__"

        return "llm_call"

    async def route_after_tools(
        state: ReactState,
    ) -> Literal["dispatch_tools", "llm_call", "__end__"]:
        if state.get("tool_phase") == "execute":
            return "dispatch_tools"
        if inject_queue is not None and not inject_queue.empty():
            return "llm_call"
        if state.get("is_done") and inject_queue is None:
            return "__end__"
        if state.get("is_done") and inject_queue is not None and inject_queue.empty():
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
    graph.add_node("dispatch_tools", dispatch_tools)
    for slot in range(TOOL_BATCH_SIZE):
        graph.add_node(f"tool_exec_{slot}", tool_exec)
    graph.add_node("tools_join", tools_join)

    graph.add_edge(START, "llm_call")
    graph.add_conditional_edges(
        "llm_call",
        route_after_llm,
        {
            "llm_call": "llm_call",
            "dispatch_tools": "dispatch_tools",
            "__end__": END,
        },
    )
    graph.add_conditional_edges("dispatch_tools", route_tool_batch)
    graph.add_edge(
        [f"tool_exec_{slot}" for slot in range(TOOL_BATCH_SIZE)],
        "tools_join",
    )
    graph.add_conditional_edges(
        "tools_join",
        route_after_tools,
        {
            "llm_call": "llm_call",
            "dispatch_tools": "dispatch_tools",
            "__end__": END,
        },
    )

    compiled = graph.compile(checkpointer=checkpointer)

    # Wrap ainvoke to normalize completion state.
    _original_ainvoke = compiled.ainvoke

    async def _wrapped_ainvoke(*args, **kwargs):
        result = await _original_ainvoke(*args, **kwargs)
        if "__interrupt__" in result:
            outcomes = sorted(
                result.get("tool_outcomes", []),
                key=lambda outcome: outcome["index"],
            )
            if active_audit is not None:
                for outcome in outcomes:
                    active_audit.record_tool_call(
                        tool_name=outcome["tool_name"],
                        tool_args=outcome["tool_args"],
                        tool_result=outcome["payload"],
                        success=bool(outcome["success"]),
                        latency_ms=outcome["latency_ms"],
                    )
                await _finish_active_audit()
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
