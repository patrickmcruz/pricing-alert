from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from uuid import UUID

from src.core.execution import RunStatus, ScraperRunRecord, SkuRunRecord, SkuRunStatus


class ExecutionRepository(ABC):
    """
    Abstract interface for persisting scraper run/execution state, so a UI
    can observe what's running, what finished, and recent history - separate
    from PriceRepository, which only holds scraped price data.
    """

    @abstractmethod
    async def start_run(self, store_name: str) -> UUID:
        """Records a new run as RUNNING and returns its run_id."""

    @abstractmethod
    async def finish_run(
        self,
        run_id: UUID,
        status: RunStatus,
        listings_total: int,
        listings_succeeded: int,
        listings_failed: int,
        error_message: Optional[str] = None,
    ) -> None:
        """Marks a run as finished (SUCCESS or FAILED) with final counters."""

    @abstractmethod
    async def get_latest_runs(self) -> List[ScraperRunRecord]:
        """Returns the most recent run for each store that has ever run."""

    @abstractmethod
    async def get_run_history(self, limit: int = 50) -> List[ScraperRunRecord]:
        """Returns the most recent runs across all stores, newest first."""

    @abstractmethod
    async def fail_stale_running_runs(self, error_message: str) -> int:
        """
        Marks any run still RUNNING as FAILED. Meant to be called once at
        startup: a RUNNING row can only be legitimate if the orchestrator
        process that started it is still alive, so after a restart every such
        row is provably orphaned (the process died mid-run without reaching
        finish_run) - left alone it would show as "running" forever in the
        UI. Returns the count of rows reset.
        """

    @abstractmethod
    async def start_sku_run(
        self, run_id: UUID, store_name: str, product_url: str, product_title: str
    ) -> UUID:
        """Records a single SKU attempt within a run as RUNNING, returns its sku_run_id."""

    @abstractmethod
    async def finish_sku_run(
        self, sku_run_id: UUID, status: SkuRunStatus, error_message: Optional[str] = None
    ) -> None:
        """Marks a SKU attempt as finished, with its outcome."""

    @abstractmethod
    async def get_current_sku_run(self, run_id: UUID) -> Optional[SkuRunRecord]:
        """
        Returns the SKU attempt still RUNNING for this run, if any. There's at
        most one, since the per-SKU loop in PriceEngine.run_scraper is sequential.
        """

    @abstractmethod
    async def get_sku_run_counts(self, run_id: UUID) -> Dict[SkuRunStatus, int]:
        """
        Returns a count of SKU attempts per status for this run - the live
        progress readout ("5/12 done"), computed straight from sku_runs
        instead of waiting for scraper_runs' totals, which are only written
        once at the very end of the run.
        """

    @abstractmethod
    async def fail_stale_running_sku_runs(self, error_message: str) -> int:
        """
        Same rationale as fail_stale_running_runs, for sku_runs: a SKU attempt
        left RUNNING after a restart is provably orphaned. Returns the count
        of rows reset.
        """
