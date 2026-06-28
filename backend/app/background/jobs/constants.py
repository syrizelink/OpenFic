"""Background job constants."""

from typing import Final

JOB_TYPE_SESSION_TITLE: Final = "session_title"
JOB_TYPE_CHAPTER_SUMMARY: Final = "chapter_summary"
JOB_TYPE_LONG_TERM_SUMMARY: Final = "long_term_summary"
JOB_TYPE_SUMMARY_BATCH: Final = "summary_batch"
JOB_TYPE_RETRIEVAL_CHAPTER_INDEX_BATCH: Final = "retrieval_chapter_index_batch"

JOB_QUEUE_LLM: Final = "llm"
JOB_QUEUE_DEFAULT: Final = "default"
