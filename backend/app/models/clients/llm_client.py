# -*- coding: utf-8 -*-
"""
LLM Client - LLM模型调用客户端。

使用LangChain组件提供流式和非流式的LLM聊天调用接口。
"""

import asyncio
import time
from dataclasses import dataclass
import json
import re
from typing import AsyncGenerator, Any, Mapping

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    BaseMessage,
)
from langchain_core.tools import BaseTool
from loguru import logger

from app.core.errors import LLMTimeoutError
from app.models.clients.deepseek_payload import patch_deepseek_reasoning_payload
from app.models.clients.model_factory import ModelConfig, create_chat_model


DEFAULT_LLM_TIMEOUT = 120


_patch_deepseek_reasoning_payload = patch_deepseek_reasoning_payload


@dataclass
class LLMConfig:
    """LLM调用配置。"""

    provider_type: str
    base_url: str
    api_key: str
    model_id: str
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_tokens: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    deepseek_reasoning_effort: str | None = None
    deepseek_thinking_type: str | None = None
    request_timeout: int = DEFAULT_LLM_TIMEOUT


@dataclass
class LLMResponse:
    """LLM非流式响应。"""

    content: str
    reasoning_content: str = ""
    finish_reason: str | None = None
    usage: dict | None = None
    tool_calls: list[dict[str, Any]] | None = None
    first_token_ms: int | None = None


@dataclass
class LLMStreamChunk:
    """Incremental LLM chunk for content and tool-call streaming."""

    content: str = ""
    reasoning_content: str = ""
    tool_call_chunks: list[dict[str, Any]] | None = None
    response: LLMResponse | None = None
    first_token_ms: int | None = None


class LLMClient:
    """LLM模型调用客户端，使用LangChain组件支持流式和非流式调用。"""

    def __init__(self, config: LLMConfig):
        """
        初始化LLM客户端。

        Args:
            config: LLM配置。
        """
        self.config = config
        self._llm: BaseChatModel | None = None
        self._llm_with_tools: BaseChatModel | None = None

    def _get_llm(self) -> BaseChatModel:
        """获取或创建LangChain LLM实例。"""
        if self._llm is not None:
            return self._llm

        config = self.config
        self._llm = create_chat_model(
            ModelConfig(
                provider_type=config.provider_type,
                base_url=config.base_url,
                api_key=config.api_key,
                model_id=config.model_id,
                temperature=config.temperature,
                top_p=config.top_p,
                top_k=config.top_k,
                max_tokens=config.max_tokens,
                frequency_penalty=config.frequency_penalty,
                presence_penalty=config.presence_penalty,
                deepseek_reasoning_effort=config.deepseek_reasoning_effort,
                deepseek_thinking_type=config.deepseek_thinking_type,
            )
        )

        return self._llm

    def _convert_messages(self, messages: list[dict[str, str]]) -> list[BaseMessage]:
        """将消息字典转换为LangChain消息对象。"""
        result: list[BaseMessage] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                result.append(SystemMessage(content=content))
            elif role == "assistant":
                result.append(AIMessage(content=content))
            else:
                result.append(HumanMessage(content=content))
        return result

    async def generate(
        self, messages: list[dict[str, str]], timeout: int | None = None
    ) -> LLMResponse:
        """
        非流式聊天调用。

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]。
            timeout: 超时秒数，None使用配置默认值。

        Returns:
            LLM响应。
        """
        llm = self._get_llm()
        lc_messages = self._convert_messages(messages)
        effective_timeout = timeout or self.config.request_timeout

        try:
            response = await asyncio.wait_for(
                llm.ainvoke(lc_messages),
                timeout=effective_timeout,
            )
            content = (
                response.content
                if isinstance(response.content, str)
                else str(response.content)
            )
            reasoning_content = self._extract_reasoning_content(response)

            return LLMResponse(
                content=content,
                reasoning_content=reasoning_content,
                finish_reason=response.response_metadata.get("finish_reason")
                if hasattr(response, "response_metadata")
                else None,
                usage=self._extract_usage(response),
            )
        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"LLM调用超时 ({effective_timeout}s)")
        except LLMTimeoutError:
            raise
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise

    async def generate_stream(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天调用。

        Args:
            messages: 消息列表。

        Yields:
            AI回复的内容片段。
        """
        async for chunk in self.generate_stream_chunks(messages):
            if chunk.content:
                yield chunk.content

    async def generate_stream_chunks(
        self, messages: list[dict[str, str]]
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Stream a chat call with separated content and reasoning content."""
        llm = self._get_llm()
        lc_messages = self._convert_messages(messages)

        try:
            final_chunk = None
            content_parts: list[str] = []
            reasoning_parts: list[str] = []
            async for chunk in llm.astream(lc_messages):
                final_chunk = chunk if final_chunk is None else final_chunk + chunk
                content = self._normalize_chunk_content(chunk.content)
                reasoning_content = self._extract_reasoning_content(chunk)
                if content:
                    content_parts.append(content)
                if reasoning_content:
                    reasoning_parts.append(reasoning_content)
                if content or reasoning_content:
                    yield LLMStreamChunk(
                        content=content,
                        reasoning_content=reasoning_content,
                    )
            yield LLMStreamChunk(
                response=LLMResponse(
                    content="".join(content_parts),
                    reasoning_content="".join(reasoning_parts),
                    usage=self._extract_usage(final_chunk),
                )
            )
        except Exception as e:
            logger.error(f"LLM流式调用失败: {e}")
            raise

    async def generate_with_tools_stream(
        self, messages: list[BaseMessage], timeout: int | None = None
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """Stream a tool-enabled chat call and finish with a normalized response."""
        if not self._llm_with_tools:
            raise ValueError("必须先调用bind_tools()绑定工具")

        effective_timeout = timeout or self.config.request_timeout
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_call_chunks_by_index: dict[int, dict[str, Any]] = {}
        tool_call_chunks_without_index: list[dict[str, Any]] = []
        final_chunk = None
        start_time = time.perf_counter()
        first_token_ms: int | None = None

        try:
            logger.info(f"流式调用LLM (with tools), 消息数: {len(messages)}")

            async with asyncio.timeout(effective_timeout):
                async for chunk in self._llm_with_tools.astream(messages):
                    final_chunk = chunk if final_chunk is None else final_chunk + chunk
                    content = self._normalize_chunk_content(chunk.content)
                    reasoning_content = self._extract_reasoning_content(chunk)
                    tool_call_chunks = self._extract_tool_call_chunks(chunk)
                    if first_token_ms is None:
                        first_token_ms = int((time.perf_counter() - start_time) * 1000)

                    if content:
                        content_parts.append(content)
                    if reasoning_content:
                        reasoning_parts.append(reasoning_content)
                    if tool_call_chunks:
                        self._merge_tool_call_chunks(
                            tool_call_chunks_by_index,
                            tool_call_chunks_without_index,
                            tool_call_chunks,
                        )

                    if content or reasoning_content or tool_call_chunks:
                        yield LLMStreamChunk(
                            content=content,
                            reasoning_content=reasoning_content,
                            tool_call_chunks=tool_call_chunks or None,
                            first_token_ms=first_token_ms,
                        )

            response = self._build_stream_response(
                final_chunk=final_chunk,
                content="".join(content_parts),
                reasoning_content="".join(reasoning_parts),
                tool_call_chunks_by_index=tool_call_chunks_by_index,
                tool_call_chunks_without_index=tool_call_chunks_without_index,
            )
            yield LLMStreamChunk(response=response)
        except TimeoutError:
            raise LLMTimeoutError(f"LLM工具流式调用超时 ({effective_timeout}s)")
        except LLMTimeoutError:
            raise
        except Exception as e:
            logger.error(f"LLM工具流式调用失败: {e}")
            import traceback

            logger.error(traceback.format_exc())
            raise

    async def generate_with_tools(
        self, messages: list[BaseMessage], timeout: int | None = None
    ) -> LLMResponse:
        """Run a non-streaming tool-enabled chat call."""
        if not self._llm_with_tools:
            raise ValueError("必须先调用bind_tools()绑定工具")

        effective_timeout = timeout or self.config.request_timeout
        try:
            response = await asyncio.wait_for(
                self._llm_with_tools.ainvoke(messages),
                timeout=effective_timeout,
            )
            content = self._normalize_chunk_content(response.content)
            tool_calls = None
            if getattr(response, "tool_calls", None):
                tool_calls = [
                    {
                        "id": self._tool_call_id(tool_call, index),
                        "name": tool_call.get("name", ""),
                        "args": self._normalize_tool_args(tool_call.get("args", {})),
                    }
                    for index, tool_call in enumerate(response.tool_calls)
                ]
            return LLMResponse(
                content=content,
                reasoning_content=self._extract_reasoning_content(response),
                finish_reason=response.response_metadata.get("finish_reason")
                if hasattr(response, "response_metadata")
                else None,
                usage=self._extract_usage(response),
                tool_calls=tool_calls,
            )
        except asyncio.TimeoutError:
            raise LLMTimeoutError(f"LLM工具调用超时 ({effective_timeout}s)")
        except LLMTimeoutError:
            raise
        except Exception as e:
            logger.error(f"LLM工具调用失败: {e}")
            raise

    @staticmethod
    def _normalize_chunk_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if not content:
            return ""
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "".join(parts)
        return str(content)

    @classmethod
    def _extract_reasoning_content(cls, message_or_chunk: Any) -> str:
        parts: list[str] = []
        for source_name in ("additional_kwargs", "response_metadata"):
            source = getattr(message_or_chunk, source_name, None)
            if isinstance(source, dict):
                parts.append(
                    cls._normalize_chunk_content(source.get("reasoning_content"))
                )

        parts.append(
            cls._normalize_chunk_content(
                getattr(message_or_chunk, "reasoning_content", None)
            )
        )

        return "".join(part for part in parts if part)

    @staticmethod
    def _extract_tool_call_chunks(chunk: Any) -> list[dict[str, Any]]:
        raw_chunks = getattr(chunk, "tool_call_chunks", None) or []
        result: list[dict[str, Any]] = []
        for raw_chunk in raw_chunks:
            if isinstance(raw_chunk, dict):
                result.append(dict(raw_chunk))
        return result

    @classmethod
    def _extract_usage(cls, message_or_chunk: Any) -> dict[str, Any] | None:
        usage = getattr(message_or_chunk, "usage_metadata", None)
        if isinstance(usage, dict) and usage:
            return dict(usage)

        response_metadata = getattr(message_or_chunk, "response_metadata", None)
        if isinstance(response_metadata, dict):
            metadata_usage = response_metadata.get("usage") or response_metadata.get(
                "token_usage"
            )
            if isinstance(metadata_usage, dict) and metadata_usage:
                return dict(metadata_usage)
        return None

    @staticmethod
    def _merge_tool_call_chunks(
        by_index: dict[int, dict[str, Any]],
        without_index: list[dict[str, Any]],
        chunks: list[dict[str, Any]],
    ) -> None:
        for chunk in chunks:
            index = chunk.get("index")
            if not isinstance(index, int):
                without_index.append(dict(chunk))
                continue

            current = by_index.setdefault(
                index,
                {"id": "", "name": "", "args": "", "index": index},
            )
            if chunk.get("id"):
                current["id"] = chunk.get("id")
            if chunk.get("name"):
                current["name"] = chunk.get("name")
            if chunk.get("args"):
                current["args"] = f"{current.get('args') or ''}{chunk.get('args')}"

    @staticmethod
    def _repair_json_string(value: str) -> str:
        result: list[str] = []
        in_string = False
        escaped = False
        length = len(value)
        for index, char in enumerate(value):
            if not in_string:
                result.append(char)
                if char == '"':
                    in_string = True
                continue

            if escaped:
                result.append(char)
                escaped = False
                continue
            if char == "\\":
                result.append(char)
                escaped = True
                continue
            if char == '"':
                cursor = index + 1
                while cursor < length and value[cursor].isspace():
                    cursor += 1
                if cursor >= length or value[cursor] in {",", "}", "]", ":"}:
                    result.append(char)
                    in_string = False
                else:
                    result.append('\\"')
                continue
            if char == "\n":
                result.append("\\n")
                continue
            result.append(char)
        return "".join(result)

    @classmethod
    def _parse_tool_args(cls, args_raw: str) -> dict[str, Any]:
        candidates = [args_raw]
        match = re.search(r"\{.*\}", args_raw, re.DOTALL)
        if match:
            candidates.append(match.group(0))
        candidates.extend(
            cls._repair_json_string(candidate) for candidate in list(candidates)
        )
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        return {"_raw": args_raw}

    @classmethod
    def _normalize_tool_args(cls, args: Any) -> dict[str, Any]:
        if isinstance(args, dict):
            raw_args = args.get("_raw")
            if isinstance(raw_args, str) and raw_args.strip():
                repaired = cls._parse_tool_args(raw_args)
                if "_raw" not in repaired:
                    return repaired
            return args
        if isinstance(args, str) and args.strip():
            return cls._parse_tool_args(args)
        return {}

    @staticmethod
    def _tool_call_id(tool_call: Mapping[str, Any], index: int) -> str:
        return str(tool_call.get("id") or f"call_{index}")

    @classmethod
    def _build_stream_response(
        cls,
        *,
        final_chunk: Any,
        content: str,
        reasoning_content: str,
        tool_call_chunks_by_index: dict[int, dict[str, Any]],
        tool_call_chunks_without_index: list[dict[str, Any]],
    ) -> LLMResponse:
        tool_calls = None
        if final_chunk is not None and getattr(final_chunk, "tool_calls", None):
            tool_calls = [
                {
                    "id": cls._tool_call_id(tc, index),
                    "name": tc.get("name", ""),
                    "args": cls._normalize_tool_args(tc.get("args", {})),
                    "_stream_index": index,
                }
                for index, tc in enumerate(final_chunk.tool_calls)
            ]

        if not tool_calls:
            merged_chunks = (
                list(tool_call_chunks_by_index.values())
                + tool_call_chunks_without_index
            )
            tool_calls = []
            for chunk in merged_chunks:
                name = str(chunk.get("name") or "")
                args_raw = chunk.get("args") or ""
                if not name and not args_raw:
                    continue
                args: dict[str, Any] = {}
                if isinstance(args_raw, str) and args_raw.strip():
                    args = cls._parse_tool_args(args_raw)
                tool_calls.append(
                    {
                        "id": str(
                            chunk.get("id")
                            or f"call_{chunk.get('index', len(tool_calls))}"
                        ),
                        "name": name,
                        "args": args,
                    }
                )

            if not tool_calls:
                tool_calls = None

        finish_reason = None
        if final_chunk is not None and hasattr(final_chunk, "response_metadata"):
            metadata = final_chunk.response_metadata
            finish_reason = metadata.get("finish_reason")

        return LLMResponse(
            content=content,
            reasoning_content=reasoning_content,
            finish_reason=finish_reason,
            usage=cls._extract_usage(final_chunk),
            tool_calls=tool_calls,
        )

    def bind_tools(self, tools: list[BaseTool]) -> "LLMClient":
        """
        绑定工具到LLM。

        Args:
            tools: 工具列表。

        Returns:
            返回self以支持链式调用。
        """
        llm = self._get_llm()
        self._llm_with_tools = llm.bind_tools(tools)  # type: ignore[assignment]
        logger.info(f"已绑定 {len(tools)} 个工具到LLM")
        return self
