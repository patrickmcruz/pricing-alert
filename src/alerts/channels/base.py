from abc import ABC, abstractmethod

from src.alerts.contracts import AlertEvent


class NotificationChannel(ABC):
    """A pluggable delivery mechanism for triggered AlertEvents."""

    @abstractmethod
    async def send(self, event: AlertEvent) -> None:
        """Delivers the event. Raises on failure - AlertDispatcher isolates per-channel errors."""
