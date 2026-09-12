# -*- coding: utf-8 -*-
"""Tool schemas for structured summary generation."""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class ChapterSummaryToolArgs(BaseModel):
    start_time: str = Field(description="Waktu mulai")
    end_time: str = Field(description="Waktu selesai")
    characters: list[str] = Field(description="Daftar tokoh")
    locations: list[str] = Field(description="Daftar lokasi")
    summary: str = Field(description="Ringkasan bab")


class LongTermSummaryToolArgs(BaseModel):
    start_time: str = Field(description="Waktu mulai")
    end_time: str = Field(description="Waktu selesai")
    summary: str = Field(description="Ringkasan agregat")


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
        description="Kirim ringkasan bab terstruktur. Wajib dipanggil dan hanya sekali.",
        args_schema=ChapterSummaryToolArgs,
    )


def make_long_term_summary_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=emit_long_term_summary,
        name="emit_long_term_summary",
        description=(
            "Kirim ringkasan jangka jauh terstruktur. Wajib dipanggil dan hanya sekali."
        ),
        args_schema=LongTermSummaryToolArgs,
    )
