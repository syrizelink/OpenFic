from langchain_core.messages import ToolMessage

from app.agent_runtime.runner.event_scope import is_subagent_child_event
from app.agent_runtime.tool_call_recovery import (
    build_malformed_tool_call_error,
    is_malformed_tool_call,
    recover_message_tool_calls,
    synthesize_tool_call_id,
    tool_call_input,
)


class EventTranslator:
    def __init__(
        self,
        session_id: str,
        *,
        allow_subagent_child_events: bool = False,
    ):
        self.session_id = session_id
        self._allow_subagent_child_events = allow_subagent_child_events
        self._streaming_tool_calls: dict[tuple[str, int], dict[str, str]] = {}

    def translate(self, event: dict) -> dict | list[dict] | None:
        if (
            is_subagent_child_event(event)
            and not self._allow_subagent_child_events
        ):
            return None

        kind = event.get("event")

        if kind == "on_chat_model_stream":
            chunk = event["data"].get("chunk")
            events: list[dict] = []
            reasoning_content = self._extract_reasoning_content(chunk)
            if reasoning_content:
                events.append(
                    {
                        "name": "agent:reasoning",
                        "data": {
                            "session_id": self.session_id,
                            "run_id": event.get("run_id"),
                            "content": reasoning_content,
                        },
                    }
                )
            events.extend(self._extract_streaming_tool_call_events(event, chunk))
            content = getattr(chunk, "content", "") if chunk else ""
            if content:
                events.append(
                    {
                        "name": "agent:token",
                        "data": {
                            "session_id": self.session_id,
                            "run_id": event.get("run_id"),
                            "content": content,
                        },
                    }
                )
            if not events:
                return None
            if len(events) == 1:
                return events[0]
            return events

        if kind == "on_tool_start":
            tool_call_id = self._extract_tool_call_id(event)
            return {
                "name": "agent:tool_call",
                "data": {
                    "session_id": self.session_id,
                    "run_id": event.get("run_id"),
                    "tool_call_id": tool_call_id,
                    "tool": event.get("name"),
                    "input": event.get("data", {}).get("input"),
                },
            }

        if kind == "on_tool_end":
            output = self._normalize_tool_output(event.get("data", {}).get("output"))
            tool_call_id = self._extract_tool_call_id(event) or (
                output.get("tool_call_id") if isinstance(output, dict) else None
            )
            return {
                "name": "agent:tool_result",
                "data": {
                    "session_id": self.session_id,
                    "run_id": event.get("run_id"),
                    "tool_call_id": tool_call_id,
                    "tool": event.get("name"),
                    "input": event.get("data", {}).get("input"),
                    "output": output,
                },
            }

        if kind == "on_tool_error" and self._allow_subagent_child_events:
            tool_call_id = self._extract_tool_call_id(event)
            return {
                "name": "agent:tool_result",
                "data": {
                    "session_id": self.session_id,
                    "run_id": event.get("run_id"),
                    "tool_call_id": tool_call_id,
                    "tool": event.get("name"),
                    "input": event.get("data", {}).get("input"),
                    "output": {
                        "type": "ok",
                        "success": True,
                        "reason": "approval_preview",
                        "message": "需要审批",
                        "tool_call_id": tool_call_id,
                        "tool_name": event.get("name"),
                    },
                },
            }

        if kind == "on_chat_model_end":
            output = event.get("data", {}).get("output")
            events = self._extract_unrecoverable_tool_result_events(event, output)
            self._clear_streaming_tool_calls(event.get("run_id"))
            usage = self._extract_usage(output)
            if usage is not None:
                events.append(
                    {
                        "name": "agent:usage",
                        "data": {
                            "session_id": self.session_id,
                            "usage": usage,
                        },
                    }
                )
            if not events:
                return None
            if len(events) == 1:
                return events[0]
            return events

        return None

    def _extract_streaming_tool_call_events(
        self, event: dict, chunk: object | None
    ) -> list[dict]:
        if chunk is None:
            return []

        tool_call_chunks = getattr(chunk, "tool_call_chunks", None) or []
        if not isinstance(tool_call_chunks, list):
            return []

        run_id = str(event.get("run_id") or "default")
        events: list[dict] = []
        for raw in tool_call_chunks:
            if not isinstance(raw, dict):
                continue
            index = raw.get("index")
            if not isinstance(index, int):
                continue
            state = self._streaming_tool_calls.setdefault(
                (run_id, index), {"id": "", "name": "", "args_text": ""}
            )
            raw_id = raw.get("id")
            raw_name = raw.get("name")
            raw_args = raw.get("args")
            if isinstance(raw_id, str) and raw_id:
                state["id"] = raw_id
            if isinstance(raw_name, str) and raw_name:
                state["name"] = raw_name
            partial_args = raw_args if isinstance(raw_args, str) else ""
            if partial_args:
                state["args_text"] = f"{state.get('args_text') or ''}{partial_args}"

            tool_call_id = state.get("id")
            tool_name = state.get("name")
            if not tool_call_id and tool_name:
                tool_call_id = synthesize_tool_call_id(
                    index=index,
                    id_seed=run_id,
                    name=tool_name,
                )
                state["id"] = tool_call_id
            if not tool_call_id or not tool_name:
                continue
            events.append(
                {
                    "name": "agent:tool_call",
                    "data": {
                        "session_id": self.session_id,
                        "run_id": event.get("run_id"),
                        "tool_call_id": tool_call_id,
                        "tool": tool_name,
                        "partial_args": partial_args,
                        "args_text": state.get("args_text") or "",
                        "is_delta": True,
                    },
                }
            )
        return events

    def _extract_unrecoverable_tool_result_events(
        self,
        event: dict,
        output: object | None,
    ) -> list[dict]:
        run_id = str(event.get("run_id") or "default")
        events: list[dict] = []
        for tool_call in recover_message_tool_calls(output, id_seed=run_id):
            if not is_malformed_tool_call(tool_call):
                continue
            events.append(
                {
                    "name": "agent:tool_result",
                    "data": {
                        "session_id": self.session_id,
                        "run_id": event.get("run_id"),
                        "tool_call_id": tool_call.get("id"),
                        "tool": tool_call.get("name"),
                        "input": tool_call_input(tool_call),
                        "output": build_malformed_tool_call_error(tool_call),
                    },
                }
            )
        return events

    def _clear_streaming_tool_calls(self, run_id: object) -> None:
        normalized_run_id = str(run_id or "default")
        for key in [
            key for key in self._streaming_tool_calls if key[0] == normalized_run_id
        ]:
            del self._streaming_tool_calls[key]

    @staticmethod
    def _extract_reasoning_content(chunk: object | None) -> str:
        if chunk is None:
            return ""

        direct = getattr(chunk, "reasoning_content", None)
        if isinstance(direct, str) and direct:
            return direct

        additional_kwargs = getattr(chunk, "additional_kwargs", None)
        if isinstance(additional_kwargs, dict):
            for key in ("reasoning_content", "reasoning"):
                value = additional_kwargs.get(key)
                if isinstance(value, str) and value:
                    return value

        response_metadata = getattr(chunk, "response_metadata", None)
        if isinstance(response_metadata, dict):
            for key in ("reasoning_content", "reasoning"):
                value = response_metadata.get(key)
                if isinstance(value, str) and value:
                    return value

        return ""

    @staticmethod
    def _extract_usage(output: object | None) -> dict | None:
        if output is None:
            return None

        usage = getattr(output, "usage_metadata", None)
        if isinstance(usage, dict) and usage:
            return dict(usage)
        if usage is not None and hasattr(usage, "items"):
            usage_dict = dict(usage)
            if usage_dict:
                return usage_dict

        response_metadata = getattr(output, "response_metadata", None)
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

    @staticmethod
    def _normalize_tool_output(output: object | None) -> object | None:
        if output is None:
            return None
        if isinstance(output, ToolMessage):
            payload: dict[str, object | None] = {
                "content": output.content,
                "tool_call_id": output.tool_call_id,
                "name": output.name,
                "status": getattr(output, "status", None),
            }
            return payload
        return output

    @staticmethod
    def _extract_tool_call_id(event: dict) -> str | None:
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            return None

        direct = metadata.get("tool_call_id")
        if isinstance(direct, str) and direct:
            return direct

        tool_call = metadata.get("tool_call")
        if isinstance(tool_call, dict):
            nested = tool_call.get("id")
            if isinstance(nested, str) and nested:
                return nested

        return None
