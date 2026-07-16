# -*- coding: utf-8 -*-
"""Structured summary generation using tool calls."""

import json
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import AuditContext
from app.core.errors import NotFoundError
from app.macro.compiler import EntryInput, PromptChainCompiler
from app.memory.chapter.summary_tools import (
    make_chapter_summary_tool,
    make_long_term_summary_tool,
)
from app.models.clients import LLMClient
from app.storage.models.chapter import Chapter
from app.storage.models.chapter_summary import ChapterSummary
from app.storage.repos import chapter_repo, chapter_summary_repo
from app.storage.services import prompt_chain_service


@dataclass(frozen=True)
class GeneratedChapterSummary:
    start_time: str
    end_time: str
    characters: list[str]
    locations: list[str]
    summary: str
    token_count: int


@dataclass(frozen=True)
class GeneratedLongTermSummary:
    start_time: str
    end_time: str
    summary: str
    token_count: int


@dataclass(frozen=True)
class ChapterSummaryPrompt:
    messages: list[SystemMessage]


@dataclass(frozen=True)
class LongTermSummaryPrompt:
    messages: list[SystemMessage]
    summaries_text: str


async def _get_prompt_entries(
    session: AsyncSession,
    prompt_id: str,
) -> list[EntryInput]:
    result = await prompt_chain_service.get_latest_version_with_entries_or_default(
        session, prompt_id
    )
    entries = [entry for entry in result.entries if entry.is_enabled]
    if not entries:
        raise NotFoundError(f"提示词链 {prompt_id} 没有条目")
    return [
        EntryInput(
            role=entry.role,
            content=entry.content,
            order_index=entry.order_index,
            is_enabled=entry.is_enabled,
        )
        for entry in entries
    ]


async def _build_system_messages(
    session: AsyncSession,
    *,
    prompt_id: str,
) -> list[SystemMessage]:
    compiler = PromptChainCompiler()
    compile_result = await compiler.compile(entries=await _get_prompt_entries(session, prompt_id))

    messages = [
        SystemMessage(content=entry.content)
        for entry in compile_result.entries
        if entry.role == "system" and entry.content
    ]
    return messages


def _xml_tag(name: str, value: str) -> str:
    return f"<{name}>{escape(value)}</{name}>"


def _summary_list_value(value: str) -> str:
    try:
        items = json.loads(value)
    except json.JSONDecodeError:
        return ""
    return value if isinstance(items, list) and items else ""


def _previous_chapter_message(chapter: Chapter, summary: ChapterSummary | None) -> str:
    parts = [
        _xml_tag("title", chapter.title) if chapter.title else "",
        _xml_tag("start_time", summary.start_time) if summary and summary.start_time else "",
        _xml_tag("end_time", summary.end_time) if summary and summary.end_time else "",
        _xml_tag("characters", _summary_list_value(summary.characters_json)) if summary else "",
        _xml_tag("locations", _summary_list_value(summary.locations_json)) if summary else "",
        _xml_tag("content", chapter.content) if chapter.content else "",
    ]
    content = "\n  ".join(part for part in parts if part)
    return (
        "以下部分是上一个章节的有关内容，用以帮助你连贯的理解剧情信息，该部分与你要总结的内容**无关**。\n"
        "<previous_chapter>\n"
        f"  {content}\n"
        "</previous_chapter>"
    )


def _target_chapter_message(chapter: Chapter) -> str:
    return (
        "以下部分是你需要总结的章节内容。\n"
        "<target_chapter>\n"
        f"  {_xml_tag('title', chapter.title)}\n"
        f"  {_xml_tag('content', chapter.content)}\n"
        "</target_chapter>"
    )


def _summaries_target_message(chapter_summaries: str) -> str:
    return "以下部分是你需要总结的摘要内容\n" f"{chapter_summaries}"


def _usage_token_count(usage: dict[str, Any] | None, fallback_text: str) -> int:
    if usage:
        for key in ("total_tokens", "total_token_count", "input_tokens"):
            value = usage.get(key)
            if isinstance(value, int) and value > 0:
                return value
    return max(1, len(fallback_text) // 2) if fallback_text else 0


def _first_tool_args(tool_calls: list[dict[str, Any]] | None, tool_name: str) -> dict[str, Any]:
    for call in tool_calls or []:
        if call.get("name") == tool_name and isinstance(call.get("args"), dict):
            return call["args"]
    raise ValueError(f"模型未调用必需工具: {tool_name}")


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


async def build_chapter_summary_prompt(
    session: AsyncSession,
    chapter_id: str,
) -> ChapterSummaryPrompt:
    chapter = await chapter_repo.get_by_id(session, chapter_id)
    if not chapter:
        raise NotFoundError(f"章节不存在: {chapter_id}")

    messages = await _build_system_messages(
        session,
        prompt_id="memory-chapter-summary",
    )
    chapters = await chapter_repo.list_by_volume(session, chapter.volume_id)
    previous_chapter = next((item for item in reversed(chapters) if item.order < chapter.order), None)
    if previous_chapter:
        previous_summary = await chapter_summary_repo.get_by_chapter_id(session, previous_chapter.id)
        messages.append(SystemMessage(content=_previous_chapter_message(previous_chapter, previous_summary)))
    messages.append(SystemMessage(content=_target_chapter_message(chapter)))
    return ChapterSummaryPrompt(messages=messages)


async def generate_chapter_summary_from_prompt(
    llm_client: LLMClient,
    prompt: ChapterSummaryPrompt,
    *,
    audit_context: AuditContext,
    model_id: str,
    model_provider: str | None,
    model_name: str | None,
) -> GeneratedChapterSummary:
    llm_client.bind_tools([make_chapter_summary_tool()])
    logger.info("生成结构化章节摘要")
    messages: list[BaseMessage] = [
        *prompt.messages,
        HumanMessage(content="请调用 emit_chapter_summary 输出结果。"),
    ]
    async with audit_context.llm_call(
        operation="chapter_summary",
        model_id=model_id,
        model_provider=model_provider,
        model_name=model_name,
        request_messages=messages,
    ) as audit:
        response = await llm_client.generate_with_tools(messages, timeout=120)
        audit.record_response(
            content=response.content,
            tool_calls=response.tool_calls,
            usage=response.usage,
        )
    args = _first_tool_args(response.tool_calls, "emit_chapter_summary")
    summary = _clean_text(args.get("summary"))
    if not summary:
        raise ValueError("章节摘要为空")
    return GeneratedChapterSummary(
        start_time=_clean_text(args.get("start_time")),
        end_time=_clean_text(args.get("end_time")),
        characters=_clean_list(args.get("characters")),
        locations=_clean_list(args.get("locations")),
        summary=summary,
        token_count=_usage_token_count(response.usage, summary),
    )


async def build_long_term_summary_prompt(
    session: AsyncSession,
    chapter_summaries: list[ChapterSummary],
    chapters: list[Chapter],
) -> LongTermSummaryPrompt:
    chapter_by_id = {chapter.id: chapter for chapter in chapters}
    parts: list[str] = []
    for index, item in enumerate(
        sorted(chapter_summaries, key=lambda summary: summary.chapter_order or 0),
        start=1,
    ):
        chapter = chapter_by_id.get(item.chapter_id or "")
        title = chapter.title if chapter else f"第{item.chapter_order}章"
        characters = _summary_list_value(item.characters_json)
        locations = _summary_list_value(item.locations_json)
        summary_parts = [
            _xml_tag("title", title),
            _xml_tag("start_time", item.start_time) if item.start_time else "",
            _xml_tag("end_time", item.end_time) if item.end_time else "",
            _xml_tag("characters", characters) if characters else "",
            _xml_tag("locations", locations) if locations else "",
            _xml_tag("content", item.summary),
        ]
        content = "\n    ".join(part for part in summary_parts if part)
        parts.append(
            f"  <sum{index}>\n"
            f"    {content}\n"
            f"  </sum{index}>"
        )
    if not parts:
        raise NotFoundError("没有可聚合的章节摘要")
    summaries_text = "<target_summaries>\n" + "\n".join(parts) + "\n</target_summaries>"

    messages = await _build_system_messages(
        session,
        prompt_id="memory-range-summary",
    )
    messages.append(SystemMessage(content=_summaries_target_message(summaries_text)))
    return LongTermSummaryPrompt(messages=messages, summaries_text=summaries_text)


async def generate_long_term_summary_from_prompt(
    llm_client: LLMClient,
    prompt: LongTermSummaryPrompt,
    *,
    audit_context: AuditContext,
    model_id: str,
    model_provider: str | None,
    model_name: str | None,
) -> GeneratedLongTermSummary:
    llm_client.bind_tools([make_long_term_summary_tool()])
    logger.info("生成结构化远期摘要")
    messages: list[BaseMessage] = [
        *prompt.messages,
        HumanMessage(content="请调用 emit_long_term_summary 输出结果。"),
    ]
    async with audit_context.llm_call(
        operation="long_term_summary",
        model_id=model_id,
        model_provider=model_provider,
        model_name=model_name,
        request_messages=messages,
    ) as audit:
        response = await llm_client.generate_with_tools(messages, timeout=120)
        audit.record_response(
            content=response.content,
            tool_calls=response.tool_calls,
            usage=response.usage,
        )
    args = _first_tool_args(response.tool_calls, "emit_long_term_summary")
    summary = _clean_text(args.get("summary"))
    if not summary:
        raise ValueError("远期摘要为空")
    return GeneratedLongTermSummary(
        start_time=_clean_text(args.get("start_time")),
        end_time=_clean_text(args.get("end_time")),
        summary=summary,
        token_count=_usage_token_count(response.usage, summary),
    )
