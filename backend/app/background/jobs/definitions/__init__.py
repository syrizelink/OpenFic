"""Register background job definitions."""

from collections.abc import Callable

from app.background.jobs.constants import (
    JOB_TYPE_CHAPTER_SUMMARY,
    JOB_TYPE_LONG_TERM_SUMMARY,
    JOB_TYPE_RETRIEVAL_CHAPTER_INDEX_BATCH,
    JOB_TYPE_SESSION_TITLE,
    JOB_TYPE_SUMMARY_BATCH,
)
from app.background.runtime.registry import get_job_registry


def register_session_title_job() -> None:
    from app.background.jobs.definitions.session_title import SESSION_TITLE_JOB

    get_job_registry().register(SESSION_TITLE_JOB)


def register_chapter_summary_job() -> None:
    from app.background.jobs.definitions.chapter_summary import CHAPTER_SUMMARY_JOB

    get_job_registry().register(CHAPTER_SUMMARY_JOB)


def register_long_term_summary_job() -> None:
    from app.background.jobs.definitions.long_term_summary import LONG_TERM_SUMMARY_JOB

    get_job_registry().register(LONG_TERM_SUMMARY_JOB)


def register_summary_batch_job() -> None:
    from app.background.jobs.definitions.summary_batch import SUMMARY_BATCH_JOB

    get_job_registry().register(SUMMARY_BATCH_JOB)


def register_retrieval_chapter_index_batch_job() -> None:
    from app.background.jobs.definitions.retrieval_chapter_index_batch import (
        RETRIEVAL_CHAPTER_INDEX_BATCH_JOB,
    )

    get_job_registry().register(RETRIEVAL_CHAPTER_INDEX_BATCH_JOB)


_REGISTRARS: dict[str, Callable[[], None]] = {
    JOB_TYPE_SESSION_TITLE: register_session_title_job,
    JOB_TYPE_CHAPTER_SUMMARY: register_chapter_summary_job,
    JOB_TYPE_LONG_TERM_SUMMARY: register_long_term_summary_job,
    JOB_TYPE_SUMMARY_BATCH: register_summary_batch_job,
    JOB_TYPE_RETRIEVAL_CHAPTER_INDEX_BATCH: register_retrieval_chapter_index_batch_job,
}


def register_background_job_type(job_type: str) -> None:
    registrar = _REGISTRARS.get(job_type)
    if registrar is None:
        return
    registrar()


def register_all_background_jobs() -> None:
    """Register built-in background job definitions."""
    for registrar in _REGISTRARS.values():
        registrar()


__all__ = [
    "register_background_job_type",
    "register_all_background_jobs",
]
