"""MessagePersister: 订阅 LangGraph astream_events 写库。"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import repo
from app.agent_runtime.persistence.child_runs import (
    get_child_run_agent_number,
    get_child_run_for_parent_dispatch_id,
    get_child_run_for_parent_tool_call,
)
from app.agent_runtime.persistence.errors import PersistenceWriteError
from app.agent_runtime.runner.event_scope import is_subagent_child_event
from app.agent_runtime.tool_call_recovery import (
    build_malformed_tool_call_error,
    is_malformed_tool_call,
    reconcile_tool_call_chunks,
    recover_message_tool_calls,
)

logger = logging.getLogger(__name__)


@dataclass
class _AssistantBuffer:
    run_id: str
    agent_id: str | None
    content_parts: list[str] = field(default_factory=list)
    reasoning_parts: list[str] = field(default_factory=list)
    reasoning_started_at: datetime | None = None
    reasoning_last_updated_at: datetime | None = None
    tool_call_chunks: dict[int, dict] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class _PendingTool:
    run_id: str
    tool_call_id: str
    tool_name: str
    args: dict[str, object]


class MessagePersister:
    """订阅 LangGraph astream_events，将消息写入 agent_run_messages。"""

    AGENT_NODE_TAG = "agent_node"

    def __init__(
        self,
        session_id: str,
        task_id: str,
        project_id: str,
        db_session_factory: Callable[[], AsyncSession],
        *,
        allow_subagent_child_events: bool = False,
    ):
        self.session_id = session_id
        self.task_id = task_id
        self.project_id = project_id
        self._make_session = db_session_factory
        self._allow_subagent_child_events = allow_subagent_child_events
        self._current_agent_id: str | None = None
        self._assistant_buffers: dict[str, _AssistantBuffer] = {}
        self._pending_tools: dict[str, _PendingTool] = {}
        self._previewed_tool_runs: set[str] = set()

    async def handle(self, event: dict) -> None:
        if is_subagent_child_event(event) and not self._allow_subagent_child_events:
            return

        kind = event.get("event")
        try:
            if kind == "on_chain_start":
                self._on_chain_start(event)
            elif kind == "on_chat_model_start":
                self._on_chat_model_start(event)
            elif kind == "on_chat_model_stream":
                self._on_chat_model_stream(event)
            elif kind == "on_chat_model_end":
                await self._on_chat_model_end(event)
            elif kind == "on_tool_start":
                self._on_tool_start(event)
            elif kind == "on_tool_end":
                await self._on_tool_end(event)
            elif kind == "on_tool_error" and self._allow_subagent_child_events:
                await self._on_tool_error(event)
        except PersistenceWriteError:
            raise
        except Exception as e:
            logger.exception("MessagePersister.handle failed for event %s", kind)
            raise PersistenceWriteError(
                f"persister handle failed for event={kind}"
            ) from e

    def _on_chain_start(self, event: dict) -> None:
        if self.AGENT_NODE_TAG in event.get("tags", []):
            self._current_agent_id = event.get("name")

    def _on_chat_model_start(self, event: dict) -> None:
        run_id = event.get("run_id") or "default"
        self._assistant_buffers[run_id] = _AssistantBuffer(
            run_id=run_id, agent_id=self._current_agent_id
        )

    def _on_chat_model_stream(self, event: dict) -> None:
        run_id = event.get("run_id") or "default"
        buf = self._assistant_buffers.get(run_id)
        if buf is None:
            buf = _AssistantBuffer(run_id=run_id, agent_id=self._current_agent_id)
            self._assistant_buffers[run_id] = buf

        chunk = event.get("data", {}).get("chunk")
        if chunk is None:
            return

        content = getattr(chunk, "content", "") or ""
        if isinstance(content, str) and content:
            buf.content_parts.append(content)

        reasoning = (getattr(chunk, "additional_kwargs", {}) or {}).get(
            "reasoning_content"
        )
        if reasoning:
            chunk_received_at = datetime.now(UTC)
            if buf.reasoning_started_at is None:
                buf.reasoning_started_at = chunk_received_at
            buf.reasoning_last_updated_at = chunk_received_at
            buf.reasoning_parts.append(reasoning)

        tcc_list = getattr(chunk, "tool_call_chunks", None) or []
        for tcc in tcc_list:
            idx = tcc.get("index")
            if idx is None:
                continue
            slot = buf.tool_call_chunks.setdefault(
                idx, {"id": None, "name": None, "args_text": ""}
            )
            if tcc.get("id"):
                slot["id"] = tcc["id"]
            if tcc.get("name"):
                slot["name"] = tcc["name"]
            args_part = tcc.get("args")
            if args_part:
                slot["args_text"] += args_part

    async def _on_chat_model_end(self, event: dict) -> None:
        run_id = event.get("run_id") or "default"
        buf = self._assistant_buffers.pop(run_id, None)
        if buf is None:
            return

        output = event.get("data", {}).get("output")
        content = "".join(buf.content_parts) or self._extract_output_content(output)
        reasoning = "".join(buf.reasoning_parts) or self._extract_output_reasoning(
            output
        )
        reasoning_duration_ms = self._get_reasoning_duration_ms(buf)
        tool_calls = self._reconcile_tool_calls(buf.tool_call_chunks, run_id=run_id)
        if not tool_calls:
            tool_calls = self._extract_output_tool_calls(output, run_id=run_id)

        if not content and not reasoning and not tool_calls:
            return

        await self._write(
            role="assistant",
            status="complete",
            content=content,
            reasoning=reasoning,
            reasoning_duration_ms=reasoning_duration_ms,
            tool_calls=tool_calls or None,
            agent_id=buf.agent_id,
        )

        for tool_call in tool_calls:
            if not is_malformed_tool_call(tool_call):
                continue
            await self._write(
                role="tool",
                status="complete",
                content=json.dumps(
                    build_malformed_tool_call_error(tool_call),
                    ensure_ascii=False,
                ),
                tool_call_id=tool_call["id"],
                tool_name=tool_call["name"],
            )

    def _on_tool_start(self, event: dict) -> None:
        run_id = event.get("run_id") or "default"
        tool_name = event.get("name") or ""
        meta = event.get("metadata") or {}
        tool_call_id = (
            meta.get("tool_call_id") or meta.get("tool_call", {}).get("id") or run_id
        )
        input_data = event.get("data", {}).get("input")
        self._pending_tools[run_id] = _PendingTool(
            run_id=run_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            args=input_data if isinstance(input_data, dict) else {},
        )

    async def _on_tool_end(self, event: dict) -> None:
        run_id = event.get("run_id") or "default"
        pending = self._pending_tools.pop(run_id, None)
        self._previewed_tool_runs.discard(run_id)
        output = event.get("data", {}).get("output")
        tool_call_id = (
            pending.tool_call_id
            if pending is not None
            else self._extract_tool_call_id(event, output)
        )
        if isinstance(output, str):
            content = output
        else:
            content = json.dumps(output, ensure_ascii=False, default=str)
        await self._write(
            role="tool",
            status="complete",
            content=content,
            tool_call_id=tool_call_id,
            tool_name=pending.tool_name if pending else event.get("name"),
        )

    async def _on_tool_error(self, event: dict) -> None:
        run_id = event.get("run_id") or "default"
        pending = self._pending_tools.get(run_id)
        tool_call_id = (
            pending.tool_call_id
            if pending is not None
            else self._extract_tool_call_id(event, event.get("data", {}).get("error"))
        )
        tool_name = pending.tool_name if pending else event.get("name")
        if not tool_call_id or not tool_name:
            return

        self._previewed_tool_runs.add(run_id)
        await self._write(
            role="tool",
            status="complete",
            content=json.dumps(
                {
                    "type": "ok",
                    "success": True,
                    "reason": "approval_preview",
                    "message": "需要审批",
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                },
                ensure_ascii=False,
            ),
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )

    async def persist_node_event(self, payload: dict) -> None:
        if payload.get("session_id") != self.session_id:
            return

        phase = payload.get("phase")
        node = payload.get("node")
        node_status = payload.get("status")
        if phase not in {"start", "end"} or not isinstance(node, str) or not node:
            return
        if node_status not in {"running", "completed", "error"}:
            return

        message_type = "node_start" if phase == "start" else "node_end"
        await self._write(
            role="system",
            status="complete",
            content="",
            agent_id=node,
            message_type=message_type,
            display_channel="hidden",
            metadata={
                "kind": "agent_node",
                "event_type": message_type,
                "node": node,
                "phase": phase,
                "node_status": node_status,
                "current_node": payload.get("current_node"),
                "previous_node": payload.get("previous_node"),
            },
        )

    @staticmethod
    def _reconcile_tool_calls(
        chunks: dict[int, dict],
        *,
        run_id: str | None = None,
    ) -> list[dict]:
        return reconcile_tool_call_chunks(chunks, id_seed=run_id)

    @staticmethod
    def _extract_output_content(output: object | None) -> str:
        content = getattr(output, "content", "")
        return content if isinstance(content, str) else ""

    @staticmethod
    def _extract_output_reasoning(output: object | None) -> str | None:
        direct = getattr(output, "reasoning_content", None)
        if isinstance(direct, str) and direct:
            return direct

        additional_kwargs = getattr(output, "additional_kwargs", None)
        if isinstance(additional_kwargs, dict):
            for key in ("reasoning_content", "reasoning"):
                value = additional_kwargs.get(key)
                if isinstance(value, str) and value:
                    return value

        response_metadata = getattr(output, "response_metadata", None)
        if isinstance(response_metadata, dict):
            for key in ("reasoning_content", "reasoning"):
                value = response_metadata.get(key)
                if isinstance(value, str) and value:
                    return value

        return None

    @staticmethod
    def _extract_output_tool_calls(
        output: object | None,
        *,
        run_id: str | None = None,
    ) -> list[dict]:
        return recover_message_tool_calls(output, id_seed=run_id)

    async def _write(self, **kwargs) -> None:
        session = self._make_session()
        try:
            await repo.insert_message(
                session,
                session_id=self.session_id,
                task_id=self.task_id,
                project_id=self.project_id,
                **kwargs,
            )
        finally:
            await session.close()

    async def mark_user_sent(self, message_id: str) -> None:
        session = self._make_session()
        try:
            await repo.update_status(session, message_id, "sent")
        finally:
            await session.close()

    async def apply_interrupt_preview(self, payload: dict) -> None:
        preview_items = payload.get("tool_result_previews")
        if isinstance(preview_items, list):
            for preview_item in preview_items:
                if not isinstance(preview_item, dict):
                    continue
                await self.apply_interrupt_preview(
                    {
                        "tool_call_id": preview_item.get("tool_call_id"),
                        "tool_name": preview_item.get("tool_name"),
                        "tool_result_preview": preview_item.get("preview"),
                    }
                )

        tool_call_id = payload.get("tool_call_id")
        tool_result_preview = payload.get("tool_result_preview")
        tool_name = payload.get("tool_name")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            return
        if not isinstance(tool_result_preview, dict):
            return

        session = self._make_session()
        try:
            content = json.dumps(tool_result_preview, ensure_ascii=False)
            try:
                await repo.update_latest_tool_message_content(
                    session,
                    session_id=self.session_id,
                    tool_call_id=tool_call_id,
                    content=content,
                )
            except PersistenceWriteError as exc:
                if "tool message not found" not in str(exc):
                    raise
                await repo.insert_message(
                    session,
                    session_id=self.session_id,
                    task_id=self.task_id,
                    project_id=self.project_id,
                    role="tool",
                    status="complete",
                    content=content,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name if isinstance(tool_name, str) else None,
                )
        finally:
            await session.close()

    async def finalize(self, reason: Literal["done", "cancelled", "error"]) -> None:
        """run/resume 结束时把 buffer 里未提交的 partial / aborted 写库。"""
        try:
            for run_id, buf in list(self._assistant_buffers.items()):
                content = "".join(buf.content_parts)
                reasoning = "".join(buf.reasoning_parts) or None
                reasoning_duration_ms = self._get_reasoning_duration_ms(buf)
                tool_calls = self._reconcile_tool_calls(
                    buf.tool_call_chunks,
                    run_id=run_id,
                )

                if not content and not reasoning and not tool_calls:
                    continue

                await self._write(
                    role="assistant",
                    status="partial",
                    content=content,
                    reasoning=reasoning,
                    reasoning_duration_ms=reasoning_duration_ms,
                    tool_calls=tool_calls or None,
                    agent_id=buf.agent_id,
                )
                for tc in tool_calls:
                    await self._write(
                        role="tool",
                        status="aborted",
                        content="[中断] 工具未执行",
                        tool_call_id=tc["id"],
                        tool_name=tc["name"],
                    )

            self._assistant_buffers.clear()

            for pending in list(self._pending_tools.values()):
                if pending.run_id in self._previewed_tool_runs:
                    continue
                content = await self._cancelled_subagent_tool_result(
                    pending,
                    reason=reason,
                )
                await self._write(
                    role="tool",
                    status="aborted",
                    content=content or "[中断] 工具执行未完成",
                    tool_call_id=pending.tool_call_id,
                    tool_name=pending.tool_name,
                )
            self._pending_tools.clear()
            self._previewed_tool_runs.clear()
        except PersistenceWriteError:
            raise
        except Exception as e:
            logger.exception("MessagePersister.finalize failed reason=%s", reason)
            raise PersistenceWriteError(
                f"persister finalize failed reason={reason}"
            ) from e

    async def _cancelled_subagent_tool_result(
        self,
        pending: _PendingTool,
        *,
        reason: Literal["done", "cancelled", "error"],
    ) -> str | None:
        if reason != "cancelled" or pending.tool_name not in {
            "dispatch_subagent",
            "notify_subagent",
        }:
            return None

        session = self._make_session()
        try:
            child_run = await get_child_run_for_parent_tool_call(
                session,
                parent_session_id=self.session_id,
                tool_call_id=pending.tool_call_id,
            )
            if child_run is None and pending.tool_name == "notify_subagent":
                dispatch_id = pending.args.get("dispatch_id")
                if isinstance(dispatch_id, str) and dispatch_id:
                    child_run = await get_child_run_for_parent_dispatch_id(
                        session,
                        parent_session_id=self.session_id,
                        dispatch_id=dispatch_id,
                    )
        finally:
            await session.close()
        if child_run is None or not child_run.is_active:
            return None

        return json.dumps(
            {
                "dispatch_id": child_run.dispatch_id,
                "agent_key": child_run.agent_key,
                "agent_number": get_child_run_agent_number(child_run.metadata_json),
                "error": "subagent 会话已被用户中断，要通知其继续工作请使用 notify_subagent",
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _get_reasoning_duration_ms(buf: _AssistantBuffer) -> int | None:
        if not buf.reasoning_parts:
            return None
        started_at = buf.reasoning_started_at
        if started_at is None:
            return None
        ended_at = buf.reasoning_last_updated_at or started_at
        elapsed = ended_at - started_at
        return max(0, int(elapsed.total_seconds() * 1000))

    @staticmethod
    def _extract_tool_call_id(
        event: dict,
        output: object | None = None,
    ) -> str | None:
        metadata = event.get("metadata")
        if isinstance(metadata, dict):
            direct = metadata.get("tool_call_id")
            if isinstance(direct, str) and direct:
                return direct
            tool_call = metadata.get("tool_call")
            if isinstance(tool_call, dict):
                nested = tool_call.get("id")
                if isinstance(nested, str) and nested:
                    return nested

        if output is None:
            return None
        tool_call_id = getattr(output, "tool_call_id", None)
        if isinstance(tool_call_id, str) and tool_call_id:
            return tool_call_id
        if isinstance(output, dict):
            direct = output.get("tool_call_id")
            if isinstance(direct, str) and direct:
                return direct
            tool_call = output.get("tool_call")
            if isinstance(tool_call, dict):
                nested = tool_call.get("id")
                if isinstance(nested, str) and nested:
                    return nested
        return None
