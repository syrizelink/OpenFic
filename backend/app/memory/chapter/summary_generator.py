# -*- coding: utf-8 -*-
"""Structured summary generation using tool calls."""

from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.macro.compiler import EntryInput, PromptChainCompiler
from app.memory.chapter.sequence import global_order_index
from app.memory.chapter.summary_tools import (
    make_chapter_summary_tool,
    make_long_term_summary_tool,
)
from app.models.clients import LLMClient
from app.storage.models.chapter import Chapter
from app.storage.models.chapter_summary import ChapterSummary
from app.storage.repos import chapter_repo, volume_repo
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
    task_name: str,
) -> list[EntryInput]:
    result = await prompt_chain_service.get_latest_version_with_entries_or_default(
        session, "memory", task_name, None
    )
    entries = [entry for entry in result.entries if entry.is_enabled]
    if not entries:
        raise NotFoundError(f"提示词链 memory/{task_name} 没有条目")
    return [
        EntryInput(
            role=entry.role,
            content=entry.content,
            order_index=entry.order_index,
            is_enabled=entry.is_enabled,
        )
        for entry in entries
    ]


async def _build_prompt_messages(
    session: AsyncSession,
    *,
    task_name: str,
    project_id: str | None,
    chapter_id: str | None,
    target_xml: str,
) -> list[SystemMessage]:
    compiler = PromptChainCompiler(session)
    compile_result = await compiler.compile(
        entries=await _get_prompt_entries(session, task_name),
        project_id=project_id,
        chapter_id=chapter_id,
    )

    messages = [
        SystemMessage(content=entry.content)
        for entry in compile_result.entries
        if entry.role == "system" and entry.content
    ]
    messages.append(SystemMessage(content=target_xml))
    return messages


def _chapter_target_message(chapter: Chapter) -> str:
    return (
        "<target>\n"
        f"  <chapter_title>{escape(chapter.title)}</chapter_title>\n"
        f"  <chapter_content>{escape(chapter.content)}</chapter_content>\n"
        "</target>"
    )


def _summaries_target_message(chapter_summaries: str) -> str:
    return (
        "<target>\n"
        f"  <summaries>{escape(chapter_summaries)}</summaries>\n"
        "</target>"
    )


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


async def generate_chapter_summary(
    session: AsyncSession,
    llm_client: LLMClient,
    chapter_id: str,
) -> GeneratedChapterSummary:
    prompt = await build_chapter_summary_prompt(session, chapter_id)
    return await generate_chapter_summary_from_prompt(llm_client, prompt)


async def build_chapter_summary_prompt(
    session: AsyncSession,
    chapter_id: str,
) -> ChapterSummaryPrompt:
    chapter = await chapter_repo.get_by_id(session, chapter_id)
    if not chapter:
        raise NotFoundError(f"章节不存在: {chapter_id}")

    messages = await _build_prompt_messages(
        session,
        task_name="mid_range_summary",
        project_id=chapter.project_id,
        chapter_id=chapter.id,
        target_xml=_chapter_target_message(chapter),
    )
    return ChapterSummaryPrompt(messages=messages)


async def generate_chapter_summary_from_prompt(
    llm_client: LLMClient,
    prompt: ChapterSummaryPrompt,
) -> GeneratedChapterSummary:
    llm_client.bind_tools([make_chapter_summary_tool()])
    logger.info("生成结构化章节摘要")
    response = await llm_client.generate_with_tools(
        [*prompt.messages, HumanMessage(content="请调用 emit_chapter_summary 输出结果。")],
        timeout=120,
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


async def generate_long_term_summary(
    session: AsyncSession,
    llm_client: LLMClient,
    chapter_summaries: list[ChapterSummary],
    chapters: list[Chapter],
) -> GeneratedLongTermSummary:
    prompt = await build_long_term_summary_prompt(session, chapter_summaries, chapters)
    return await generate_long_term_summary_from_prompt(llm_client, prompt)


async def build_long_term_summary_prompt(
    session: AsyncSession,
    chapter_summaries: list[ChapterSummary],
    chapters: list[Chapter],
) -> LongTermSummaryPrompt:
    chapter_by_id = {chapter.id: chapter for chapter in chapters}
    parts: list[str] = []
    for item in sorted(chapter_summaries, key=lambda summary: summary.chapter_order or 0):
        chapter = chapter_by_id.get(item.chapter_id or "")
        title = chapter.title if chapter else f"第{item.chapter_order}章"
        parts.append(
            f"<chapter{item.chapter_order}>\n{title}\n时间：{item.start_time} - {item.end_time}\n人物：{item.characters_json}\n地点：{item.locations_json}\n摘要：{item.summary}\n</chapter{item.chapter_order}>"
        )
    summaries_text = "\n\n".join(parts)
    if not summaries_text:
        raise NotFoundError("没有可聚合的章节摘要")

    project_id = chapters[0].project_id if chapters else None
    anchor_chapter_id: str | None = None
    if chapters:
        volumes = await volume_repo.list_by_project(session, project_id or "")
        order_map = global_order_index(chapters, volumes)
        latest_chapter = max(
            chapters, key=lambda ch: order_map.get(ch.id, -1), default=None
        )
        if latest_chapter is not None:
            anchor_chapter_id = latest_chapter.id
    messages = await _build_prompt_messages(
        session,
        task_name="far_range_summary",
        project_id=project_id,
        chapter_id=anchor_chapter_id,
        target_xml=_summaries_target_message(summaries_text),
    )
    return LongTermSummaryPrompt(messages=messages, summaries_text=summaries_text)


async def generate_long_term_summary_from_prompt(
    llm_client: LLMClient,
    prompt: LongTermSummaryPrompt,
) -> GeneratedLongTermSummary:
    llm_client.bind_tools([make_long_term_summary_tool()])
    logger.info("生成结构化远期摘要")
    response = await llm_client.generate_with_tools(
        [*prompt.messages, HumanMessage(content="请调用 emit_long_term_summary 输出结果。")],
        timeout=120,
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
