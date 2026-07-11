import asyncio
import json
import logging
import os
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.contract import StoreConfig
from src.core.browser import BrowserFactory
from src.core.config import settings
from src.engine.scheduler import PriceEngine
from src.engine.discovery import DiscoveryEngine
from src.repositories.sqlite_repository import SQLitePriceRepository
from src.scrapers.kabum import KabumScraper
from src.scrapers.terabyte import TerabyteScraper
from src.scrapers.mercadolivre import MercadoLivreScraper
from src.spiders.kabum_spider import KabumSpider
from src.spiders.terabyte_spider import TerabyteSpider

level_str = getattr(settings, 'log_level', 'INFO').upper()
logging_level = getattr(logging, level_str, logging.INFO)

logging.basicConfig(
    level=logging_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/orchestrator.log", encoding="utf-8")
    ],
    force=True
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
                target_keywords=settings.default_gpus,
                cron_times=["08:00", "12:00", "16:00", "20:00"],
            )
        )
    return configs


async def startup_routine(discovery: DiscoveryEngine, engine: PriceEngine, configs: list[StoreConfig]):
    """Runs immediately on startup to update graphs for the user."""
    logger.info("Executing immediate startup routine (Discovery + Scrapers)...")
    
    # 1. Run Discovery to find any new URLs
    await discovery.run_discovery(configs)
    
    # 2. Run all scrapers concurrently to fetch prices
    logger.info("Discovery complete. Running scrapers...")
    tasks = [engine.run_scraper(scraper) for scraper in engine.scrapers.values()]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            logger.error("A scraper failed during startup: %s", res, exc_info=res)
    
    logger.info("Startup routine complete. Initial data populated.")


async def main():
    logger.info("Initializing GPU Price Tracker Orchestrator...")

    # 1. Initialize Persistence Layer
    repository = SQLitePriceRepository(db_path=DB_PATH)
    await repository.initialize_schema()

    # 2. Initialize Dependency Factories
    client_factory = BrowserFactory()

    # 3. Initialize Engines
    scheduler = AsyncIOScheduler()
    engine = PriceEngine(
        scheduler=scheduler, repository=repository, client_factory=client_factory
    )
    discovery = DiscoveryEngine(
        repository=repository, client_factory=client_factory
    )

    # 4. Register Concrete Scrapers & Spiders
    engine.register_scrapers(
        [
            KabumScraper(),
            TerabyteScraper(),
            MercadoLivreScraper(),
        ]
    )
    
    discovery.register_spiders(
        [
            KabumSpider(),
            TerabyteSpider(),
        ]
    )

    # 5. Build Schedule
    configs = load_stores_config()
    engine.build_schedule(configs)

    # 6. Start Orchestration
    engine.start()

    logger.info("Orchestrator cron schedule started.")
    
    # 7. Run initial discovery and scrape
    await startup_routine(discovery, engine, configs)

    logger.info("Orchestrator running. Press Ctrl+C to exit.")
    
    # Block the main thread to keep the asyncio event loop alive
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down Orchestrator...")
