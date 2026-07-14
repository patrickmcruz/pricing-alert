from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
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
