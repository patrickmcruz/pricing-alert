# **ARTIFACT 5: Orchestration Engine and Temporal Scheduling**

**Target file:** `src/engine/scheduler.py`

## Overview

The orchestration engine is responsible for coordinating scraper execution according to the user-defined schedule.

Its responsibilities are intentionally limited to:

- registering scraper strategies;
- loading execution schedules;
- injecting runtime dependencies;
- coordinating scraper execution;
- persisting validated results through the repository abstraction.

The orchestration layer must remain independent of scraper implementations, HTTP clients, browser automation, database implementations, and presentation logic.

All external dependencies must be injected, allowing deterministic unit and integration tests.

```python
from __future__ import annotations

from typing import Dict, Iterable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.base_scraper import BaseScraper
from src.core.contract import StoreConfig
from src.repositories.base_repository import PriceRepository


class PriceEngine:
    """
    Coordinates scraper execution.

    This class performs orchestration only.
    """

    def __init__(
        self,
        scheduler: AsyncIOScheduler,
        repository: PriceRepository,
        client_factory,
    ):
        self.scheduler = scheduler
        self.repository = repository
        self.client_factory = client_factory
        self.scrapers: Dict[str, BaseScraper] = {}

    def register_scraper(
        self,
        scraper: BaseScraper,
    ) -> None:
        self.scrapers[scraper.store_name] = scraper

    def register_scrapers(
        self,
        scrapers: Iterable[BaseScraper],
    ) -> None:
        for scraper in scrapers:
            self.register_scraper(scraper)

    async def run_scraper(
        self,
        scraper: BaseScraper,
        keywords: list[str],
    ) -> None:
        """
        Executes a scraper for all configured keywords.
        """

        client = await self.client_factory.create(scraper)

        try:
            for keyword in keywords:
                prices = await scraper.execute(
                    keyword,
                    client,
                )

                if prices:
                    await self.repository.save_prices(prices)

        finally:
            await self.client_factory.close(client)

    def build_schedule(
        self,
        configs: list[StoreConfig],
    ) -> None:
        """
        Registers all cron jobs.
        """

        ...

    def start(self) -> None:
        self.scheduler.start()
```

---

## **Implementation Requirements**

The agent must ensure that:

- The orchestration layer is responsible only for coordinating scraper execution.
- All scraper implementations are registered dynamically.
- Scrapers are executed following the Strategy Pattern.
- Runtime dependencies are injected rather than instantiated internally.
- HTTP clients and browser contexts are created by reusable factories.
- The scheduler never instantiates HTTP clients, Playwright instances, or repositories directly.
- Persistence is performed exclusively through the `PriceRepository` abstraction.
- The scheduler remains independent of SQLite, DuckDB, or any specific database implementation.
- Multiple execution windows per day are supported through `StoreConfig`.
- Each scheduled job executes asynchronously.
- Failures in one scraper must not interrupt the execution of other scheduled jobs.
- Structured logging records job start, completion, execution time, and failures.
- Every scheduled execution is independently traceable through the associated `execution_id`.
- Resources such as HTTP clients and browser contexts are properly released after execution.
- The orchestration layer is fully testable by replacing the scheduler, repository, client factory, and scrapers with mocks or stubs.
- No network access or database connection is required to unit test the orchestration logic.
- The implementation follows the Strategy Pattern, Dependency Injection, Repository Pattern, and the Single Responsibility Principle (SRP).