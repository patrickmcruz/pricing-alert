import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, Iterable, Optional
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.base_scraper import BaseScraper, SelectorOutdatedException, StoreUnavailableException
from src.core.config import settings
from src.core.contract import PriceContract, StoreConfig
from src.core.execution import RunStatus, SKU_FAILURE_LABELS_PT, ScraperRunResult, SkuRunStatus
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
        on_price_saved: Optional[Callable[[PriceContract, str], Awaitable[None]]] = None,
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

    async def _finish_sku_run(
        self, sku_run_id: Optional[UUID], status: SkuRunStatus, error_message: Optional[str] = None
    ) -> None:
        if self.execution_repository and sku_run_id is not None:
            try:
                await self.execution_repository.finish_sku_run(sku_run_id, status, error_message)
            except Exception as e:
                logger.error("Failed to record SKU execution state: %s", e)

    async def run_scraper(
        self,
        scraper: BaseScraper,
    ) -> ScraperRunResult:
        """
        Executes a scraper for all configured URLs from the database.
        """
        logger.info("Starting execution for scraper: %s", scraper.store_name)

        started_at = datetime.now(timezone.utc)
        run_id = (
            await self.execution_repository.start_run(scraper.store_name)
            if self.execution_repository
            else None
        )
        listings_succeeded = 0
        listings_failed = 0
        failure_breakdown: Counter[str] = Counter()
        run_error: Optional[str] = None
        client = None
        client_factory = None

        try:
            skus = await self.repository.get_target_skus(scraper.store_name)
            if not skus:
                logger.info("No SKUs found for store %s", scraper.store_name)
            else:
                client_factory = self.client_factories.get(scraper.transport_type)
                if client_factory is None:
                    raise UnknownTransportError(
                        f"No client factory registered for transport '{scraper.transport_type}' "
                        f"(scraper: {scraper.store_name})"
                    )

                client = await client_factory.create(scraper)

                for sku in skus:
                    sku_run_id = (
                        await self.execution_repository.start_sku_run(
                            run_id, scraper.store_name, str(sku.product_url), sku.product_title
                        )
                        if self.execution_repository and run_id is not None
                        else None
                    )
                    try:
                        logger.info("Scraping %s...", sku.product_url)
                        # A single hung page (network stall, dead browser process, an
                        # anti-bot loop that never resolves) must never block the rest
                        # of this store's SKUs - or the whole run - indefinitely.
                        price = await asyncio.wait_for(
                            scraper.execute(sku, client),
                            timeout=settings.scraper_timeout_seconds,
                        )

                        if price:
                            logger.info("Extracted price for %s: %s (Available: %s)", sku.product_url, price.price_cash, price.is_available)
                            observation_ids = await self.repository.save_prices([price], scraper_run_id=run_id)
                            if self.on_price_saved and observation_ids:
                                await self.on_price_saved(price, observation_ids[0])
                            listings_succeeded += 1
                            await self._finish_sku_run(sku_run_id, SkuRunStatus.SUCCESS)
                        else:
                            logger.warning("No price extracted for %s", sku.product_url)
                            listings_failed += 1
                            failure_breakdown[SkuRunStatus.NO_PRICE.value] += 1
                            await self._finish_sku_run(sku_run_id, SkuRunStatus.NO_PRICE, "No price extracted")
                    except asyncio.TimeoutError:
                        logger.error(
                            "Scraper %s timed out after %ss on SKU '%s' - treating as failed and moving on.",
                            scraper.store_name,
                            settings.scraper_timeout_seconds,
                            sku.product_url,
                        )
                        listings_failed += 1
                        failure_breakdown[SkuRunStatus.TIMEOUT.value] += 1
                        await self._finish_sku_run(
                            sku_run_id, SkuRunStatus.TIMEOUT,
                            f"Timed out after {settings.scraper_timeout_seconds}s",
                        )
                    except SelectorOutdatedException as e:
                        logger.critical(
                            "SelectorOutdatedException caught for %s on SKU '%s': %s",
                            scraper.store_name,
                            sku.product_url,
                            e,
                        )
                        listings_failed += 1
                        failure_breakdown[SkuRunStatus.SELECTOR_OUTDATED.value] += 1
                        await self._finish_sku_run(sku_run_id, SkuRunStatus.SELECTOR_OUTDATED, str(e))
                    except StoreUnavailableException as e:
                        # Deliberately logger.warning, not .critical/.error like the
                        # other failure branches - a store being down is an external,
                        # expected-to-recur condition, not a code/selector problem to
                        # page anyone about. See StoreUnavailableException's docstring.
                        logger.warning(
                            "Store %s appears to be down (SKU '%s'): %s",
                            scraper.store_name,
                            sku.product_url,
                            e,
                        )
                        listings_failed += 1
                        failure_breakdown[SkuRunStatus.STORE_UNAVAILABLE.value] += 1
                        await self._finish_sku_run(sku_run_id, SkuRunStatus.STORE_UNAVAILABLE, str(e))
                    except Exception as e:
                        logger.error(
                            "Scraper %s failed on SKU '%s': %s",
                            scraper.store_name,
                            sku.product_url,
                            e,
                            exc_info=True
                        )
                        listings_failed += 1
                        failure_breakdown[SkuRunStatus.FAILED.value] += 1
                        await self._finish_sku_run(sku_run_id, SkuRunStatus.FAILED, str(e))

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

            duration_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
            listings_total = listings_succeeded + listings_failed
            status = RunStatus.FAILED if run_error else RunStatus.SUCCESS

            if self.execution_repository and run_id is not None:
                try:
                    await self.execution_repository.finish_run(
                        run_id,
                        status,
                        listings_total=listings_total,
                        listings_succeeded=listings_succeeded,
                        listings_failed=listings_failed,
                        error_message=run_error,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to record execution state for %s: %s", scraper.store_name, e
                    )

            # One clean, scannable line per run instead of digging through the
            # per-SKU chatter above - this is the line that actually answers
            # "did this store's run work" at a glance.
            if run_error:
                logger.error("✗ %s: falhou - %s (%.1fs)", scraper.store_name, run_error, duration_seconds)
            elif listings_total == 0:
                logger.info("○ %s: nenhum SKU para processar (%.1fs)", scraper.store_name, duration_seconds)
            elif listings_failed == 0:
                logger.info("✓ %s: %d/%d SKUs OK (%.1fs)", scraper.store_name, listings_succeeded, listings_total, duration_seconds)
            else:
                breakdown_str = ", ".join(
                    f"{SKU_FAILURE_LABELS_PT.get(reason, reason)}={count}"
                    for reason, count in failure_breakdown.items()
                )
                logger.warning(
                    "⚠ %s: %d/%d SKUs OK, %d falharam [%s] (%.1fs)",
                    scraper.store_name, listings_succeeded, listings_total, listings_failed, breakdown_str, duration_seconds,
                )
            logger.info("Completed execution for scraper: %s", scraper.store_name)

        return ScraperRunResult(
            store_name=scraper.store_name,
            status=status,
            listings_total=listings_total,
            listings_succeeded=listings_succeeded,
            listings_failed=listings_failed,
            duration_seconds=duration_seconds,
            error_message=run_error,
            failure_breakdown=dict(failure_breakdown),
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

                    # CronTrigger resolves its own timezone independently of whatever
                    # timezone the scheduler it's added to was constructed with - if
                    # timezone= isn't passed here explicitly, APScheduler falls back to
                    # tzlocal.get_localzone() (the *container's* system tz, which is
                    # UTC), not the scheduler's tz. Every cron_time in config.toml/
                    # target-stores-list.json is a settings.display_timezone wall-clock
                    # hour, so this has to be explicit on each trigger, not just on the
                    # scheduler.
                    trigger = CronTrigger(hour=hour, minute=minute, timezone=settings.display_timezone)
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
