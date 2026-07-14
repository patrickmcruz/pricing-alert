import asyncio
import logging
from typing import Optional

from src.core.config import settings
from src.engine.scheduler import PriceEngine
from src.repositories.trigger_repository import TriggerRepository

logger = logging.getLogger(__name__)


class TriggerProcessor:
    """
    Polls TriggerRepository for "run now" requests created by the dashboard
    (which has no browser of its own) and executes them via the orchestrator's
    already-running PriceEngine (which does). Runs alongside PriceEngine's own
    cron-scheduled jobs - both go through the same run_scraper() code path, so
    both show up identically on the execution-monitor UI.
    """

    def __init__(self, trigger_repository: TriggerRepository, engine: PriceEngine):
        self.trigger_repository = trigger_repository
        self.engine = engine

    async def process_pending(self) -> None:
        pending = await self.trigger_repository.get_pending_requests()
        for request in pending:
            await self.trigger_repository.mark_processing(request.request_id)
            try:
                if request.store_name:
                    scraper = self.engine.scrapers.get(request.store_name)
                    if not scraper:
                        raise ValueError(f"No scraper registered for store '{request.store_name}'")
                    logger.info("Processing trigger request for store: %s", request.store_name)
                    await self.engine.run_scraper(scraper)
                else:
                    logger.info("Processing trigger request for all %d scraper(s)", len(self.engine.scrapers))
                    await asyncio.gather(
                        *(self.engine.run_scraper(s) for s in self.engine.scrapers.values()),
                        return_exceptions=True,
                    )
                await self.trigger_repository.mark_completed(request.request_id)
            except Exception as e:
                logger.error(
                    "Trigger request %s failed: %s", request.request_id, e, exc_info=True
                )
                await self.trigger_repository.mark_failed(request.request_id, str(e))

    async def run_forever(self, interval_seconds: Optional[float] = None) -> None:
        interval_seconds = (
            interval_seconds if interval_seconds is not None else settings.trigger_poll_interval_seconds
        )
        logger.info("Trigger processor polling every %.1fs for manual run requests.", interval_seconds)
        while True:
            try:
                await self.process_pending()
            except Exception as e:
                logger.error("Trigger processor iteration failed: %s", e, exc_info=True)
            await asyncio.sleep(interval_seconds)
