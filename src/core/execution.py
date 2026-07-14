from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ScraperRunRecord(BaseModel):
    """
    A single execution of PriceEngine.run_scraper() for one store - covers
    both cron-triggered runs and manual ones (e.g. scripts/run_all_scrapers.py),
    since both go through the same PriceEngine code path.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: UUID = Field(default_factory=uuid4)
    store_name: str
    status: RunStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    skus_total: int = 0
    skus_succeeded: int = 0
    skus_failed: int = 0
    error_message: Optional[str] = None


class ScraperRunResult(BaseModel):
    """
    What PriceEngine.run_scraper() returns to its caller once a run finishes -
    the same counts persisted via finish_run(), plus timing, so callers (e.g.
    main.py's startup_routine) can log a readable summary without a second
    round-trip to the DB.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    store_name: str
    status: RunStatus
    skus_total: int = 0
    skus_succeeded: int = 0
    skus_failed: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    # Failure reason -> count, e.g. {"timeout": 2, "selector_outdated": 1} -
    # keys match SkuRunStatus values. Lets a caller (main.py's multi-store
    # summary) show *why* a store had failures without a second DB query.
    failure_breakdown: Dict[str, int] = Field(default_factory=dict)


class SkuRunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    NO_PRICE = "no_price"
    SELECTOR_OUTDATED = "selector_outdated"


# Display-only labels for the failure_breakdown lines logged in
# src/engine/scheduler.py and main.py - keeps those summaries readable
# instead of mixing raw enum values into Portuguese sentences.
SKU_FAILURE_LABELS_PT: Dict[str, str] = {
    SkuRunStatus.FAILED.value: "erro",
    SkuRunStatus.TIMEOUT.value: "timeout",
    SkuRunStatus.NO_PRICE.value: "sem preço",
    SkuRunStatus.SELECTOR_OUTDATED.value: "seletor desatualizado",
}


class SkuRunRecord(BaseModel):
    """
    A single SKU's attempt within one ScraperRunRecord - lets the UI answer
    "is this SKU being scraped right now" and "did it finish, and how",
    which scraper_runs alone (one row per store, not per SKU) can't.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sku_run_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    store_name: str
    product_url: str
    product_title: str
    status: SkuRunStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
