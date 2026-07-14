from abc import ABC, abstractmethod
from typing import List

from src.alerts.contracts import AlertEvent, AlertRule


class AlertRepository(ABC):
    """
    Abstract interface for persisting alert rules and the history of
    triggered events. Mirrors the Repository Pattern already used by
    src/repositories/base_repository.py for price data.
    """

    @abstractmethod
    async def initialize_schema(self) -> None:
        """Creates the alert_rules/alert_history tables if they don't exist."""

    @abstractmethod
    async def save_rule(self, rule: AlertRule) -> None:
        """Persists (or replaces) an alert rule."""

    @abstractmethod
    async def get_active_rules(self) -> List[AlertRule]:
        """Retrieves all rules with is_active=True."""

    @abstractmethod
    async def save_event(self, event: AlertEvent) -> None:
        """Records a triggered alert event."""
