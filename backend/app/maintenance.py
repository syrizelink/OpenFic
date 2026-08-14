from __future__ import annotations

import time
from dataclasses import dataclass, replace
from threading import Lock


@dataclass(frozen=True)
class MaintenanceSnapshot:
    status: str
    phase: str
    progress: float | None
    deleted_rows: int
    reclaimed_pages: int
    total_pages: int
    elapsed_seconds: float
    message: str
    error: str | None


class MaintenanceState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._started_at: float | None = None
        self._snapshot = MaintenanceSnapshot(
            status="pending",
            phase="pending",
            progress=None,
            deleted_rows=0,
            reclaimed_pages=0,
            total_pages=0,
            elapsed_seconds=0.0,
            message="Waiting for local database maintenance.",
            error=None,
        )

    def start(self) -> None:
        with self._lock:
            self._started_at = time.monotonic()
            self._snapshot = replace(
                self._snapshot,
                status="running",
                phase="pruning",
                progress=None,
                deleted_rows=0,
                reclaimed_pages=0,
                total_pages=0,
                message="Pruning obsolete checkpoints.",
                error=None,
                elapsed_seconds=0.0,
            )

    def update(
        self,
        *,
        phase: str,
        message: str,
        progress: float | None,
        deleted_rows: int | None = None,
        reclaimed_pages: int | None = None,
        total_pages: int | None = None,
    ) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                status="running",
                phase=phase,
                progress=progress,
                message=message,
                deleted_rows=(
                    self._snapshot.deleted_rows
                    if deleted_rows is None
                    else deleted_rows
                ),
                reclaimed_pages=(
                    self._snapshot.reclaimed_pages
                    if reclaimed_pages is None
                    else reclaimed_pages
                ),
                total_pages=(
                    self._snapshot.total_pages
                    if total_pages is None
                    else total_pages
                ),
                error=None,
            )

    def complete(self) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                status="ready",
                phase="ready",
                progress=1.0,
                message="Local database maintenance completed.",
                error=None,
                elapsed_seconds=self._elapsed_seconds(),
            )

    def fail(self, error: str) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                status="failed",
                phase="failed",
                progress=None,
                message="Local database maintenance failed.",
                error=error,
                elapsed_seconds=self._elapsed_seconds(),
            )

    def snapshot(self) -> MaintenanceSnapshot:
        with self._lock:
            return replace(
                self._snapshot,
                elapsed_seconds=(
                    self._snapshot.elapsed_seconds
                    if self._snapshot.status in {"ready", "failed"}
                    else self._elapsed_seconds()
                ),
            )

    def is_checkpoint_locked(self) -> bool:
        """True while maintenance holds the checkpoint DB exclusively."""
        with self._lock:
            return (
                self._snapshot.status == "running"
                and self._snapshot.phase in {"migrating", "vacuuming"}
            )

    def _elapsed_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        return round(time.monotonic() - self._started_at, 3)


maintenance_state = MaintenanceState()
