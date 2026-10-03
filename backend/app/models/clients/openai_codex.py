"""Direct Responses API chat model for OpenAI Codex OAuth credentials."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
import json
from typing import Any, cast

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    SystemMessage,
    ToolMessage,
    message_chunk_to_message,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

from app.models.services.openai_codex_service import (
    OPENAI_CODEX_API_BASE_URL,
    OpenAICodexAPIError,
    OpenAICodexReauthorizationRequired,
    get_openai_codex_access_token,
)


OpenAICodexResponseError = OpenAICodexAPIError


class OpenAICodexChatModel(BaseChatModel):
    """LangChain bridge which sends only supported direct Responses fields."""

    model: str
    api_key: str = ""
    provider_id: str | None = None
    base_url: str = OPENAI_CODEX_API_BASE_URL
    reasoning_effort: str | None = None
    default_headers: dict[str, str] = Field(default_factory=dict)

    @property
    def _llm_type(self) -> str:
        return "openai-codex-responses"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "provider_id": self.provider_id,
            "base_url": self.base_url,
        }

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Any | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ):
        converted_tools = [self._responses_tool(tool) for tool in tools]
        binding_kwargs = {"tools": converted_tools, **kwargs}
        if tool_choice is not None:
            binding_kwargs["tool_choice"] = tool_choice
        return self.bind(**binding_kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager
        chunks: list[AIMessageChunk] = []
        async for generation_chunk in self._astream(messages, **kwargs):
            chunks.append(cast(AIMessageChunk, generation_chunk.message))
        if not chunks:
            raise OpenAICodexResponseError("Responses 流未返回任何消息")
        message = chunks[0]
        for chunk in chunks[1:]:
            message = message + chunk
        return ChatResult(generations=[ChatGeneration(message=message_chunk_to_message(message))])

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return asyncio.run(self._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs))

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        del stop, run_manager
        access_token = await self._access_token()
        payload = self._build_payload(
            messages,
            kwargs.get("tools"),
            kwargs.get("tool_choice"),
        )
        headers = {
            **self.default_headers,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        from app.settings import settings

        timeout = httpx.Timeout(
            timeout=settings.llm_request_timeout,
            connect=settings.llm_connect_timeout,
        )
        completed = False
        tool_calls: dict[str, dict[str, Any]] = {}
        item_call_ids: dict[str, str] = {}
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url.rstrip('/')}/responses",
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    await self._raise_http_error(response)

                async for event in _iter_sse_events(response):
                    event_type = event.get("type")
                    if event_type == "response.output_text.delta":
                        delta = event.get("delta")
                        if isinstance(delta, str) and delta:
                            yield _generation_chunk(content=delta)
                    elif event_type in {
                        "response.reasoning_summary_text.delta",
                        "response.reasoning_text.delta",
                    }:
                        delta = event.get("delta")
                        if isinstance(delta, str) and delta:
                            yield _generation_chunk(
                                additional_kwargs={"reasoning_content": delta}
                            )
                    elif event_type == "response.output_item.added":
                        item = event.get("item")
                        if isinstance(item, dict) and item.get("type") == "function_call":
                            call_id = item.get("call_id") or item.get("id")
                            name = item.get("name")
                            if isinstance(call_id, str) and isinstance(name, str):
                                index = len(tool_calls)
                                tool_calls[call_id] = {
                                    "id": call_id,
                                    "name": name,
                                    "index": index,
                                    "arguments": "",
                                }
                                if isinstance(item.get("id"), str):
                                    item_call_ids[item["id"]] = call_id
                                yield _generation_chunk(
                                    tool_call_chunks=[
                                        {
                                            "id": call_id,
                                            "name": name,
                                            "args": "",
                                            "index": index,
                                        }
                                    ]
                                )
                    elif event_type == "response.function_call_arguments.delta":
                        call_id = event.get("call_id") or item_call_ids.get(event.get("item_id"))
                        delta = event.get("delta")
                        if isinstance(call_id, str) and isinstance(delta, str):
                            call = tool_calls.get(call_id)
                            if call is None:
                                raise OpenAICodexResponseError("Responses 工具参数缺少对应调用")
                            call["arguments"] += delta
                            yield _generation_chunk(
                                tool_call_chunks=[
                                    {
                                        "args": delta,
                                        "index": call["index"],
                                    }
                                ]
                            )
                    elif event_type == "response.function_call_arguments.done":
                        call_id = event.get("call_id") or item_call_ids.get(event.get("item_id"))
                        arguments = event.get("arguments")
                        call = tool_calls.get(call_id) if isinstance(call_id, str) else None
                        if (
                            call is not None
                            and isinstance(arguments, str)
                            and not call["arguments"]
                        ):
                            call["arguments"] = arguments
                            yield _generation_chunk(
                                tool_call_chunks=[
                                    {
                                        "args": arguments,
                                        "index": call["index"],
                                    }
                                ]
                            )
                    elif event_type == "response.completed":
                        response_payload = event.get("response")
                        if isinstance(response_payload, dict):
                            if not tool_calls:
                                for index, item in enumerate(response_payload.get("output", [])):
                                    if not isinstance(item, dict) or item.get("type") != "function_call":
                                        continue
                                    call_id = item.get("call_id") or item.get("id")
                                    name = item.get("name")
                                    arguments = item.get("arguments", "")
                                    if not isinstance(call_id, str) or not isinstance(name, str):
                                        continue
                                    tool_calls[call_id] = {
                                        "id": call_id,
                                        "name": name,
                                        "index": index,
                                        "arguments": arguments if isinstance(arguments, str) else "",
                                    }
                                    yield _generation_chunk(
                                        tool_call_chunks=[
                                            {
                                                "id": call_id,
                                                "name": name,
                                                "args": tool_calls[call_id]["arguments"],
                                                "index": index,
                                            }
                                        ]
                                    )
                            usage = response_payload.get("usage")
                            metadata: dict[str, Any] = {
                                "finish_reason": "stop",
                                "response_id": response_payload.get("id"),
                            }
                            if isinstance(usage, dict):
                                metadata["usage"] = usage
                            yield _generation_chunk(
                                response_metadata=metadata,
                                usage_metadata=_usage_metadata(usage),
                                chunk_position="last",
                            )
                        completed = True
                    elif event_type in {"response.failed", "error"}:
                        raise _response_event_error(event, "Responses 请求失败")
                    elif event_type == "response.incomplete":
                        raise _response_event_error(event, "Responses 请求未完成")

        if not completed:
            raise OpenAICodexResponseError("Responses 流在 response.completed 前中断")

    async def _access_token(self) -> str:
        if self.provider_id:
            return await get_openai_codex_access_token(self.provider_id)
        if self.api_key:
            return self.api_key
        raise OpenAICodexReauthorizationRequired("OpenAI Codex 没有可用 access token")

    def _build_payload(
        self,
        messages: list[BaseMessage],
        tools: list[dict[str, Any]] | None,
        tool_choice: Any = None,
    ) -> dict[str, Any]:
        input_items: list[dict[str, Any]] = []
        instructions: list[str] = []
        for message in messages:
            if isinstance(message, SystemMessage):
                text = _text_content(message.content)
                if text:
                    instructions.append(text)
                continue
            input_items.extend(_message_to_responses_items(message))

        payload: dict[str, Any] = {
            "model": self.model,
            "input": input_items,
            "store": False,
            "stream": True,
        }
        if instructions:
            payload["instructions"] = "\n\n".join(instructions)
        if tools:
            payload["tools"] = [{
                "type": "namespace",
                "name": "openfic",
                "description": "OpenFic writing and context tools",
                "tools": tools,
            }]
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if self.reasoning_effort and self.reasoning_effort != "auto":
            payload["reasoning"] = {"effort": self.reasoning_effort}
        return payload

    @staticmethod
    def _responses_tool(tool: Any) -> dict[str, Any]:
        converted = convert_to_openai_tool(tool, strict=False)
        if converted.get("type") == "function" and isinstance(converted.get("function"), dict):
            return {"type": "function", **converted["function"]}
        return converted

    async def _raise_http_error(self, response: httpx.Response) -> None:
        request_id = response.headers.get("openai-request-id") or response.headers.get("x-request-id")
        try:
            payload = json.loads((await response.aread()).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        detail = payload.get("detail") if isinstance(payload, dict) else None
        error = payload.get("error") if isinstance(payload, dict) else None
        error = error if isinstance(error, dict) else {}
        code = error.get("code") if isinstance(error.get("code"), str) else None
        raise OpenAICodexResponseError(
            _format_response_error(
                code,
                detail or error.get("message") or f"Responses HTTP {response.status_code}",
            ),
            status_code=response.status_code,
            code=code,
            param=error.get("param") if isinstance(error.get("param"), str) else None,
            request_id=request_id,
        )


def _generation_chunk(**kwargs: Any) -> ChatGenerationChunk:
    kwargs.setdefault("content", "")
    return ChatGenerationChunk(message=AIMessageChunk(**kwargs))


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _message_to_responses_items(message: BaseMessage) -> list[dict[str, Any]]:
    if isinstance(message, ToolMessage):
        return [
            {
                "type": "function_call_output",
                "call_id": message.tool_call_id,
                "output": _text_content(message.content),
            }
        ]

    role = "assistant" if isinstance(message, AIMessage) else "user"
    content = _responses_content(message.content, role)
    items: list[dict[str, Any]] = []
    if content:
        items.append({"type": "message", "role": role, "content": content})
    if isinstance(message, AIMessage):
        for call in message.tool_calls:
            items.append(
                {
                    "type": "function_call",
                    "call_id": str(call.get("id") or "call_0"),
                    "name": str(call.get("name") or ""),
                    "namespace": "openfic",
                    "arguments": json.dumps(call.get("args") or {}, ensure_ascii=True),
                }
            )
    return items


def _responses_content(content: Any, role: str) -> str | list[dict[str, Any]]:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return _text_content(content)
    result: list[dict[str, Any]] = []
    text_type = "output_text" if role == "assistant" else "input_text"
    for item in content:
        if isinstance(item, str):
            result.append({"type": text_type, "text": item})
            continue
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "text":
            result.append({"type": text_type, "text": item.get("text", "")})
        elif item_type == "image_url":
            image_url = item.get("image_url")
            if isinstance(image_url, dict):
                image_url = image_url.get("url")
            result.append({"type": "input_image", "image_url": image_url})
        elif isinstance(item_type, str):
            result.append(dict(item))
    return result


def _usage_metadata(usage: Any) -> dict[str, Any] | None:
    if not isinstance(usage, dict):
        return None
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    metadata = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    details = usage.get("input_tokens_details")
    if isinstance(details, dict) and isinstance(details.get("cached_tokens"), int):
        metadata["input_token_details"] = {"cache_read": details["cached_tokens"]}  # type: ignore[assignment]
    return metadata


async def _iter_sse_events(response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
    data_lines: list[str] = []

    async def emit() -> dict[str, Any] | None:
        if not data_lines:
            return None
        raw = "\n".join(data_lines)
        data_lines.clear()
        if raw == "[DONE]":
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    async for line in response.aiter_lines():
        if line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").lstrip())
        elif not line.strip():
            event = await emit()
            if event is not None:
                yield event
    event = await emit()
    if event is not None:
        yield event


def _response_event_error(event: dict[str, Any], fallback: str) -> OpenAICodexResponseError:
    response = event.get("response")
    response = response if isinstance(response, dict) else {}
    error = event.get("error") or response.get("error")
    error = error if isinstance(error, dict) else {}
    code = error.get("code") or event.get("code")
    message = error.get("message") or event.get("message") or fallback
    return OpenAICodexResponseError(
        _format_response_error(code if isinstance(code, str) else None, str(message)),
        code=code if isinstance(code, str) else None,
        param=error.get("param") if isinstance(error.get("param"), str) else None,
    )


def _format_response_error(code: str | None, message: str) -> str:
    if code in {
        "subscription_sharing_usage_limit_exceeded",
        "subscription_sharing_usage_unavailable",
    }:
        return f"OpenAI Codex 用量不可用: {code}"
    return message
