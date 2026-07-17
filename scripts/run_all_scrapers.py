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

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.browser import BrowserFactory
from src.core.config import settings
from src.core.http_client import HTTPClientFactory
from src.core.logging_setup import configure_logging
from src.core.registry import get_registered_scrapers
from src.core.transport import ClientFactory
from src.db.schema import connect, initialize_schema as initialize_db_schema
from src.engine.scheduler import PriceEngine
from src.repositories.postgres_repository import PostgresPriceRepository
from src.repositories.postgres_execution_repository import PostgresExecutionRepository
import src.scrapers  # noqa: F401 - importing the package triggers @register_scraper

configure_logging(getattr(settings, "log_level", "INFO"), log_file=settings.log_file_path)
logger = logging.getLogger(__name__)


async def main() -> None:
    await initialize_db_schema(settings.db_dsn)
    repository = PostgresPriceRepository(dsn=settings.db_dsn)
    execution_repository = PostgresExecutionRepository(dsn=settings.db_dsn)

    client_factories: dict[str, ClientFactory] = {
        "browser": BrowserFactory(),
        "http": HTTPClientFactory(),
    }

    # AsyncIOScheduler is required by PriceEngine's constructor but never started -
    # this script drives run_scraper() directly instead of waiting for cron ticks.
    # execution_repository is wired the same way main.py wires it, so runs started
    # from this script show up on the execution-monitor UI page too.
    engine = PriceEngine(
        scheduler=AsyncIOScheduler(timezone=settings.display_timezone),
        repository=repository,
        client_factories=client_factories,
        execution_repository=execution_repository,
    )
    engine.register_scrapers(get_registered_scrapers().values())

    if not engine.scrapers:
        print("No scrapers registered - check src/scrapers/__init__.py auto-import.")
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

    await _print_summary(repository.dsn, started_at)


async def _print_summary(dsn: str, started_at: datetime) -> None:
    async with connect(dsn) as db:
        rows = await db.fetch(
            """
            SELECT l.slug, COUNT(*), SUM(cp.is_available::int)
            FROM price_observations cp
            JOIN listings a ON a.id = cp.listing_id
            JOIN stores l ON l.id = a.store_id
            WHERE cp.scraped_at >= $1
            GROUP BY l.slug
            """,
            started_at,
        )

    print("\n--- Summary (prices saved this run) ---")
    if not rows:
        print("No prices were saved. See the logs above for per-SKU errors.")
        return
    for store_name, total, available in rows:
        print(f"{store_name}: {total} price(s) saved ({available} available)")


if __name__ == "__main__":
    asyncio.run(main())
