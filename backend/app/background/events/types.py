"""Background event type constants."""

from typing import Final

EVENT_JOB_STARTED: Final = "background_job_started"
EVENT_JOB_PROGRESS: Final = "background_job_progress"
EVENT_JOB_SUCCEEDED: Final = "background_job_succeeded"
EVENT_JOB_FAILED: Final = "background_job_failed"
EVENT_JOB_TIMEOUT: Final = "background_job_timeout"
EVENT_JOB_CANCEL_REQUESTED: Final = "background_job_cancel_requested"
EVENT_JOB_CANCELLED: Final = "background_job_cancelled"
EVENT_JOB_RETRY_SCHEDULED: Final = "background_job_retry_scheduled"
EVENT_JOB_RECOVERED: Final = "background_job_recovered"
EVENT_JOB_SKIPPED: Final = "background_job_skipped"
EVENT_TASK_TITLE_UPDATED: Final = "task_title_updated"
EVENT_CHAPTER_SUMMARY_UPDATED: Final = "chapter_summary_updated"
EVENT_LONG_TERM_SUMMARY_UPDATED: Final = "long_term_summary_updated"
