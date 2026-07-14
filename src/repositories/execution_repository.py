from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.core.execution import RunStatus, ScraperRunRecord


class ExecutionRepository(ABC):
    """
    Abstract interface for persisting scraper run/execution state, so a UI
    can observe what's running, what finished, and recent history - separate
    from PriceRepository, which only holds scraped price data.
    """

    @abstractmethod
    async def initialize_schema(self) -> None:
        """Creates the scraper_runs table if it doesn't exist."""

    @abstractmethod
    async def start_run(self, store_name: str) -> UUID:
        """Records a new run as RUNNING and returns its run_id."""

    @abstractmethod
    async def finish_run(
        self,
        run_id: UUID,
        status: RunStatus,
        skus_total: int,
        skus_succeeded: int,
        skus_failed: int,
        error_message: Optional[str] = None,
    ) -> None:
        """Marks a run as finished (SUCCESS or FAILED) with final counters."""

    @abstractmethod
    async def get_latest_runs(self) -> List[ScraperRunRecord]:
        """Returns the most recent run for each store that has ever run."""

    @abstractmethod
    async def get_run_history(self, limit: int = 50) -> List[ScraperRunRecord]:
        """Returns the most recent runs across all stores, newest first."""
