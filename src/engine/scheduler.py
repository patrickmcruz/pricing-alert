import logging
from typing import Awaitable, Callable, Dict, Iterable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.base_scraper import BaseScraper, SelectorOutdatedException
from src.core.contract import PriceContract, StoreConfig
from src.core.execution import RunStatus
from src.core.transport import ClientFactory
from src.repositories.base_repository import PriceRepository
from src.repositories.execution_repository import ExecutionRepository

logger = logging.getLogger(__name__)


class MissingScraperError(Exception):
    """Raised when a StoreConfig marked enabled=True has no matching registered scraper."""


class UnknownTransportError(Exception):
    """Raised when a scraper's transport_type has no matching entry in client_factories."""


class PriceEngine:
    """
    Coordinates scraper execution.
    This class performs orchestration only.
    """

    def __init__(
        self,
        scheduler: AsyncIOScheduler,
        repository: PriceRepository,
        client_factories: Dict[str, ClientFactory],
        on_price_saved: Optional[Callable[[PriceContract], Awaitable[None]]] = None,
        execution_repository: Optional[ExecutionRepository] = None,
    ):
        self.scheduler = scheduler
        self.repository = repository
        self.client_factories = client_factories
        self.scrapers: Dict[str, BaseScraper] = {}
        # Optional hook fired after each price is persisted (e.g. alert evaluation).
        # PriceEngine only depends on this Callable type - never on src/alerts - so
        # orchestration stays decoupled from notification internals.
        self.on_price_saved = on_price_saved
        # Optional run/execution-state tracking (see src/ui/pages for the monitor UI).
        # Covers both cron-triggered runs and manual ones, since both call run_scraper().
        self.execution_repository = execution_repository

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

        run_id = (
            await self.execution_repository.start_run(scraper.store_name)
            if self.execution_repository
            else None
        )
        skus_succeeded = 0
        skus_failed = 0
        run_error: Optional[str] = None
        client = None
        client_factory = None

        try:
            skus = await self.repository.get_target_skus(scraper.store_name)
            if not skus:
                logger.info("No SKUs found for store %s", scraper.store_name)
                return

            client_factory = self.client_factories.get(scraper.transport_type)
            if client_factory is None:
                raise UnknownTransportError(
                    f"No client factory registered for transport '{scraper.transport_type}' "
                    f"(scraper: {scraper.store_name})"
                )

            client = await client_factory.create(scraper)

            for sku in skus:
                try:
                    logger.info("Scraping %s...", sku.product_url)
                    price = await scraper.execute(
                        sku,
                        client,
                    )

                    if price:
                        logger.info("Extracted price for %s: %s (Available: %s)", sku.product_url, price.price_cash, price.is_available)
                        await self.repository.save_prices([price])
                        if self.on_price_saved:
                            await self.on_price_saved(price)
                        skus_succeeded += 1
                    else:
                        logger.warning("No price extracted for %s", sku.product_url)
                        skus_failed += 1
                except SelectorOutdatedException as e:
                    logger.critical(
                        "SelectorOutdatedException caught for %s on SKU '%s': %s",
                        scraper.store_name,
                        sku.product_url,
                        e,
                    )
                    skus_failed += 1
                except Exception as e:
                    logger.error(
                        "Scraper %s failed on SKU '%s': %s",
                        scraper.store_name,
                        sku.product_url,
                        e,
                        exc_info=True
                    )
                    skus_failed += 1

        except Exception as e:
            logger.error(
                "Failed to initialize client or run scraper %s: %s",
                scraper.store_name,
                e,
                exc_info=True
            )
            run_error = str(e)
        finally:
            if client is not None and client_factory is not None:
                try:
                    await client_factory.close(client)
                except Exception as e:
                    logger.error(
                        "Failed to close client for %s: %s", scraper.store_name, e
                    )
            logger.info("Completed execution for scraper: %s", scraper.store_name)

            if self.execution_repository and run_id is not None:
                status = RunStatus.FAILED if run_error else RunStatus.SUCCESS
                try:
                    await self.execution_repository.finish_run(
                        run_id,
                        status,
                        skus_total=skus_succeeded + skus_failed,
                        skus_succeeded=skus_succeeded,
                        skus_failed=skus_failed,
                        error_message=run_error,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to record execution state for %s: %s", scraper.store_name, e
                    )

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
                if not config.enabled:
                    logger.info(
                        "Skipping disabled store with no scraper: %s", config.store_name
                    )
                    continue
                raise MissingScraperError(
                    f"Store '{config.store_name}' is enabled but has no registered scraper."
                )

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
