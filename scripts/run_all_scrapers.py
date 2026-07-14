"""
Manual dev/QA command: runs every registered scraper concurrently, once,
against real target sites - then prints a per-store summary.

Reuses the same DI wiring as main.py (registry auto-discovery, PriceEngine,
client_factories) but skips the scheduler ticks and the orchestrator's
infinite loop, so it exits as soon as the run completes.

Usage:
    python scripts/run_all_scrapers.py

This hits real websites - do not run it in CI. Requires target SKUs to
already exist in the DB (see scripts/seed_db.py) or discovery to have run.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

# Ensure src module is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.browser import BrowserFactory
from src.core.config import settings
from src.core.http_client import HTTPClientFactory
from src.core.registry import get_registered_scrapers
from src.core.transport import ClientFactory
from src.engine.scheduler import PriceEngine
from src.repositories.sqlite_repository import SQLitePriceRepository
from src.repositories.sqlite_execution_repository import SQLiteExecutionRepository
import src.scrappers  # noqa: F401 - importing the package triggers @register_scraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    repository = SQLitePriceRepository(db_path=settings.db_path)
    await repository.initialize_schema()

    execution_repository = SQLiteExecutionRepository(db_path=settings.db_path)
    await execution_repository.initialize_schema()

    client_factories: dict[str, ClientFactory] = {
        "browser": BrowserFactory(),
        "http": HTTPClientFactory(),
    }

    # AsyncIOScheduler is required by PriceEngine's constructor but never started -
    # this script drives run_scraper() directly instead of waiting for cron ticks.
    # execution_repository is wired the same way main.py wires it, so runs started
    # from this script show up on the execution-monitor UI page too.
    engine = PriceEngine(
        scheduler=AsyncIOScheduler(),
        repository=repository,
        client_factories=client_factories,
        execution_repository=execution_repository,
    )
    engine.register_scrapers(get_registered_scrapers().values())

    if not engine.scrapers:
        print("No scrapers registered - check src/scrappers/__init__.py auto-import.")
        return

    store_names = sorted(engine.scrapers)
    print(f"Running {len(store_names)} scraper(s) concurrently: {', '.join(store_names)}")
    started_at = datetime.now(timezone.utc)

    results = await asyncio.gather(
        *(engine.run_scraper(scraper) for scraper in engine.scrapers.values()),
        return_exceptions=True,
    )

    for store_name, result in zip(engine.scrapers.keys(), results):
        if isinstance(result, Exception):
            print(f"[{store_name}] CRASHED: {result}")

    await _print_summary(repository.db_path, started_at)


async def _print_summary(db_path: str, started_at: datetime) -> None:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT store_name, COUNT(*), SUM(is_available) FROM prices "
            "WHERE scraped_at >= ? GROUP BY store_name",
            (started_at.isoformat(),),
        )
        rows = await cursor.fetchall()

    print("\n--- Summary (prices saved this run) ---")
    if not rows:
        print("No prices were saved. See the logs above for per-SKU errors.")
        return
    for store_name, total, available in rows:
        print(f"{store_name}: {total} price(s) saved ({available} available)")


if __name__ == "__main__":
    asyncio.run(main())
