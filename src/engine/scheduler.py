import logging
from typing import Dict, Iterable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.base_scraper import BaseScraper, SelectorOutdatedException
from src.core.contract import PriceContract, StoreConfig
from src.repositories.base_repository import PriceRepository

logger = logging.getLogger(__name__)


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
        """Registers a single scraper strategy."""
        self.scrapers[scraper.store_name] = scraper
        logger.info("Registered scraper for store: %s", scraper.store_name)

    def register_scrapers(
        self,
        scrapers: Iterable[BaseScraper],
    ) -> None:
        """Registers multiple scraper strategies."""
        for scraper in scrapers:
            self.register_scraper(scraper)

    async def run_scraper(
        self,
        scraper: BaseScraper,
    ) -> None:
        """
        Executes a scraper for all configured URLs from the database.
        """
        logger.info("Starting execution for scraper: %s", scraper.store_name)
        
        skus = await self.repository.get_target_skus(scraper.store_name)
        if not skus:
            logger.info("No SKUs found for store %s", scraper.store_name)
            return

        # We assume client_factory has an async create() method, though its exact
        # signature isn't fully defined. This matches the blueprint.
        client = None
        try:
            if hasattr(self.client_factory, "create"):
                client = await self.client_factory.create(scraper)

            for sku in skus:
                try:
                    price = await scraper.execute(
                        sku,
                        client,
                    )

                    if price:
                        await self.repository.save_prices([price])
                except SelectorOutdatedException as e:
                    logger.critical(
                        "SelectorOutdatedException caught for %s on SKU '%s': %s",
                        scraper.store_name,
                        sku.product_url,
                        e,
                    )
                except Exception as e:
                    logger.error(
                        "Scraper %s failed on SKU '%s': %s",
                        scraper.store_name,
                        sku.product_url,
                        e,
                    )

        except Exception as e:
            logger.error(
                "Failed to initialize client or run scraper %s: %s",
                scraper.store_name,
                e,
            )
        finally:
            if client and hasattr(self.client_factory, "close"):
                try:
                    await self.client_factory.close(client)
                except Exception as e:
                    logger.error(
                        "Failed to close client for %s: %s", scraper.store_name, e
                    )
            logger.info("Completed execution for scraper: %s", scraper.store_name)

    def build_schedule(
        self,
        configs: list[StoreConfig],
    ) -> None:
        """
        Registers all cron jobs based on the provided configurations.
        """
        for config in configs:
            scraper = self.scrapers.get(config.store_name)
            if not scraper:
                logger.warning(
                    "No scraper registered for store: %s. Skipping schedule.",
                    config.store_name,
                )
                continue

            for cron_time in config.cron_times:
                try:
                    # cron_time format is expected to be "HH:MM"
                    hour_str, minute_str = cron_time.split(":")
                    hour = int(hour_str)
                    minute = int(minute_str)

                    trigger = CronTrigger(hour=hour, minute=minute)
                    job_id = f"scrape_{config.store_name}_{hour}_{minute}"

                    self.scheduler.add_job(
                        self.run_scraper,
                        trigger=trigger,
                        id=job_id,
                        args=[scraper],
                        replace_existing=True,
                    )
                    logger.info(
                        "Scheduled %s for %02d:%02d", config.store_name, hour, minute
                    )
                except ValueError:
                    logger.error(
                        "Invalid cron_times format '%s' for store %s. Expected HH:MM",
                        cron_time,
                        config.store_name,
                    )

    def start(self) -> None:
        """Starts the underlying asyncio scheduler."""
        logger.info("Starting PriceEngine scheduler...")
        self.scheduler.start()
