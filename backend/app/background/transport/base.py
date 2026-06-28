"""Transport contracts for background runtime."""

from abc import ABC, abstractmethod

from app.background.transport.messages import BackgroundEventMessage, JobNotification


class BackgroundTransport(ABC):
    """Transport interface used by runtime code."""

    @abstractmethod
    async def start(self) -> None:
        """Open transport resources."""

    @abstractmethod
    async def stop(self) -> None:
        """Close transport resources."""

    @abstractmethod
    async def notify_job(self, message: JobNotification) -> None:
        """Notify workers that a job exists in persistence."""

    @abstractmethod
    async def receive_job(self, timeout_ms: int) -> JobNotification | None:
        """Receive one job notification, or None on timeout."""

    @abstractmethod
    async def publish_event(self, message: BackgroundEventMessage) -> None:
        """Publish a background event."""

    @abstractmethod
    async def receive_event(self, timeout_ms: int) -> BackgroundEventMessage | None:
        """Receive one background event, or None on timeout."""
