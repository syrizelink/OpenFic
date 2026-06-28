"""Background job state constants and validation."""

from typing import Final


JOB_STATUS_PENDING: Final = "pending"
JOB_STATUS_RUNNING: Final = "running"
JOB_STATUS_SUCCEEDED: Final = "succeeded"
JOB_STATUS_FAILED: Final = "failed"
JOB_STATUS_TIMEOUT: Final = "timeout"
JOB_STATUS_CANCEL_REQUESTED: Final = "cancel_requested"
JOB_STATUS_CANCELLED: Final = "cancelled"
JOB_STATUS_SKIPPED: Final = "skipped"

TERMINAL_STATUSES: Final = frozenset(
    {
        JOB_STATUS_SUCCEEDED,
        JOB_STATUS_FAILED,
        JOB_STATUS_TIMEOUT,
        JOB_STATUS_CANCELLED,
        JOB_STATUS_SKIPPED,
    }
)

VALID_STATUS_TRANSITIONS: Final = {
    JOB_STATUS_PENDING: {JOB_STATUS_RUNNING, JOB_STATUS_SKIPPED, JOB_STATUS_CANCELLED},
    JOB_STATUS_RUNNING: {
        JOB_STATUS_SUCCEEDED,
        JOB_STATUS_FAILED,
        JOB_STATUS_TIMEOUT,
        JOB_STATUS_CANCEL_REQUESTED,
        JOB_STATUS_CANCELLED,
        JOB_STATUS_SKIPPED,
    },
    JOB_STATUS_CANCEL_REQUESTED: {JOB_STATUS_CANCELLED, JOB_STATUS_FAILED},
    JOB_STATUS_FAILED: {JOB_STATUS_PENDING},
    JOB_STATUS_TIMEOUT: {JOB_STATUS_PENDING},
}


def can_transition(current: str, next_status: str) -> bool:
    """Return whether a job can move from current to next_status."""
    return next_status in VALID_STATUS_TRANSITIONS.get(current, set())
