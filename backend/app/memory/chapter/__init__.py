# -*- coding: utf-8 -*-
"""
Chapter Context 模块 - 章节上下文构建与摘要管理。
"""

from app.memory.chapter.context_builder import (
    build_context,
    BuiltContext,
    ContextPart,
)
from app.memory.chapter.summary_generator import (
    generate_chapter_summary,
    generate_long_term_summary,
)
from app.memory.chapter.summary_service import (
    get_chapter_summary,
    list_chapter_summaries,
    list_long_term_summaries,
    enqueue_chapter_summary,
)

__all__ = [
    # Context Builder
    "build_context",
    "BuiltContext",
    "ContextPart",
    # Summary Generator
    "generate_chapter_summary",
    "generate_long_term_summary",
    # Summary Service
    "get_chapter_summary",
    "list_chapter_summaries",
    "list_long_term_summaries",
    "enqueue_chapter_summary",
]
