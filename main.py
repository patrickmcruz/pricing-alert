import asyncio
import json
import logging
import os
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.contract import StoreConfig
from src.core.browser import BrowserFactory
from src.core.http_client import HTTPClientFactory
from src.core.config import settings
from src.engine.scheduler import PriceEngine
from src.engine.discovery import DiscoveryEngine
from src.engine.trigger_processor import TriggerProcessor
from src.repositories.sqlite_repository import SQLitePriceRepository
from src.repositories.sqlite_execution_repository import SQLiteExecutionRepository
from src.repositories.sqlite_trigger_repository import SQLiteTriggerRepository
from src.core.registry import get_registered_scrapers
import src.scrappers  # noqa: F401 - importing the package triggers scraper self-registration
from src.alerts.sqlite_alert_repository import SQLiteAlertRepository
from src.alerts.dispatcher import AlertDispatcher
from src.alerts.channels.base import NotificationChannel
from src.alerts.channels.telegram import TelegramChannel

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
                enabled=store_info.get("enabled", False),
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

    alert_repository = SQLiteAlertRepository(db_path=DB_PATH)
    await alert_repository.initialize_schema()

    execution_repository = SQLiteExecutionRepository(db_path=DB_PATH)
    await execution_repository.initialize_schema()

    trigger_repository = SQLiteTriggerRepository(db_path=DB_PATH)
    await trigger_repository.initialize_schema()
    # Any request still 'processing' belonged to a previous orchestrator process
    # that no longer exists (crash, redeploy, `docker compose up` recreate) - left
    # alone it would silently block its store's (or all stores', for
    # store_name=None) trigger button forever, since nothing else ever revisits it.
    await trigger_repository.fail_stale_processing("Orphaned: orchestrator restarted while processing")

    # 2. Initialize Dependency Factories (one per transport_type a scraper may declare)
    client_factories = {
        "browser": BrowserFactory(),
        "http": HTTPClientFactory(),
    }

    # 3. Initialize Engines
    channels: list[NotificationChannel] = []
    if settings.telegram_bot_token and settings.telegram_chat_id:
        channels.append(TelegramChannel(settings.telegram_bot_token, settings.telegram_chat_id))
    else:
        logger.warning("Telegram credentials not configured - alert events will be recorded but not delivered.")
    dispatcher = AlertDispatcher(alert_repository=alert_repository, channels=channels)

    scheduler = AsyncIOScheduler()
    engine = PriceEngine(
        scheduler=scheduler,
        repository=repository,
        client_factories=client_factories,
        on_price_saved=dispatcher.handle_price,
        execution_repository=execution_repository,
    )
    discovery = DiscoveryEngine(repository=repository)
    trigger_processor = TriggerProcessor(trigger_repository=trigger_repository, engine=engine)

    # 4. Register Concrete Scrapers (auto-discovered via @register_scraper)
    engine.register_scrapers(get_registered_scrapers().values())

    # 5. Build Schedule
    configs = load_stores_config()
    engine.build_schedule(configs)

    # 6. Start Orchestration
    engine.start()

    logger.info("Orchestrator cron schedule started.")

    # Start polling for "run now" requests concurrently with the startup scrape
    # below, not after it - startup_routine can take minutes (every store's
    # SKUs, sequentially, with jitter between each), and awaiting it first would
    # silently ignore any dashboard trigger created during that whole window.
    trigger_task = asyncio.create_task(trigger_processor.run_forever())

    # 7. Run initial discovery and scrape
    await startup_routine(discovery, engine, configs)

    logger.info("Orchestrator running. Press Ctrl+C to exit.")

    # trigger_task never returns on its own - this keeps the event loop alive
    # for the rest of the process lifetime, same as before.
    await trigger_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down Orchestrator...")
