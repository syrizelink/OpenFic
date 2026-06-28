# -*- coding: utf-8 -*-
"""Tool schemas for structured summary generation."""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class ChapterSummaryToolArgs(BaseModel):
    start_time: str = Field(description="起始时间")
    end_time: str = Field(description="结束时间")
    characters: list[str] = Field(description="人物关列表")
    locations: list[str] = Field(description="地点列表")
    summary: str = Field(description="章节摘要")


class LongTermSummaryToolArgs(BaseModel):
    start_time: str = Field(description="起始时间")
    end_time: str = Field(description="结束时间")
    summary: str = Field(description="聚合摘要")


def emit_chapter_summary(
    start_time: str,
    end_time: str,
    characters: list[str],
    locations: list[str],
    summary: str,
) -> dict[str, object]:
    return {
        "start_time": start_time,
        "end_time": end_time,
        "characters": characters,
        "locations": locations,
        "summary": summary,
    }


def emit_long_term_summary(
    start_time: str,
    end_time: str,
    summary: str,
) -> dict[str, str]:
    return {"start_time": start_time, "end_time": end_time, "summary": summary}


def make_chapter_summary_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=emit_chapter_summary,
        name="emit_chapter_summary",
        description="提交结构化章节摘要。必须调用且只调用一次。",
        args_schema=ChapterSummaryToolArgs,
    )


def make_long_term_summary_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=emit_long_term_summary,
        name="emit_long_term_summary",
        description="提交结构化远期摘要。必须调用且只调用一次。",
        args_schema=LongTermSummaryToolArgs,
    )
