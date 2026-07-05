import asyncio
import json
import logging
import os
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.contract import StoreConfig
from src.core.http_client import HTTPClientFactory
from src.engine.scheduler import PriceEngine
from src.repositories.sqlite_repository import SQLitePriceRepository
from src.scrapers.kabum import KabumScraper
from src.scrapers.terabyte import TerabyteScraper

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

DB_PATH = settings.db_path


def load_stores_config() -> list[StoreConfig]:
    """Loads configuration and returns StoreConfig instances based on the JSON definitions."""
    stores_file = os.path.join("data", "target-stores-list.json")
    try:
        with open(stores_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Failed to load stores config from %s: %s", stores_file, e)
        return []

    configs = []
    # For now, we apply standard GPU keywords and a sample cron schedule to all loaded stores.
    for store_key, store_info in data.items():
        configs.append(
            StoreConfig(
                store_name=store_info["store_name"],
                target_keywords=["rtx 5070", "rtx 5070 ti"],
                cron_times=["08:00", "12:00", "16:00", "20:00"],
            )
        )
    return configs


async def main():
    logger.info("Initializing GPU Price Tracker Orchestrator...")

    # 1. Initialize Persistence Layer
    repository = SQLitePriceRepository(db_path=DB_PATH)
    await repository.initialize_schema()

    # 2. Initialize Dependency Factories
    # (These are currently empty classes from Phase 1, but this matches the architecture)
    client_factory = HTTPClientFactory()

    # 3. Initialize Scheduler Engine
    scheduler = AsyncIOScheduler()
    engine = PriceEngine(
        scheduler=scheduler, repository=repository, client_factory=client_factory
    )

    # 4. Register Concrete Scrapers
    engine.register_scrapers(
        [
            KabumScraper(),
            TerabyteScraper(),
            # Other scrapers will be added here as they are built
        ]
    )

    # 5. Build Schedule
    configs = load_stores_config()
    engine.build_schedule(configs)

    # 6. Start Orchestration
    engine.start()

    logger.info("Orchestrator running. Press Ctrl+C to exit.")

    # Block the main thread to keep the asyncio event loop alive
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down Orchestrator...")
