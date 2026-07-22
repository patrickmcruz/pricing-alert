import asyncio
import logging
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.browser import BrowserFactory
from src.core.config import settings
from src.core.http_client import HTTPClientFactory
from src.db.schema import connect
from src.engine.discovery import DiscoveryEngine
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository
from src.repositories.postgres_repository import PostgresPriceRepository
from src.repositories.postgres_target_url_repository import PostgresTargetUrlRepository
import src.spiders  # noqa: F401 - triggers spider self-registration

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

KEYWORDS = ["rtx 5070", "rtx 5070 ti", "rx 9070 oc", "rx 9070", "rx 9070 xt"]


async def main():
    dsn = settings.db_dsn
    logger.info("Connecting to database DSN: %s", dsn)

    price_repo = PostgresPriceRepository(dsn)
    catalog_repo = PostgresCatalogRepository(dsn)
    target_url_repo = PostgresTargetUrlRepository(dsn)

    discovery_engine = DiscoveryEngine(
        repository=price_repo,
        catalog_repository=catalog_repo,
        target_url_repository=target_url_repo,
    )

    browser_factory = BrowserFactory()
    http_factory = HTTPClientFactory()
    client_factories = {
        "browser": browser_factory,
        "http": http_factory,
    }

    logger.info("Starting GPU Spider Discovery for keywords: %s", KEYWORDS)
    discovered = await discovery_engine.run_spider_discovery(
        keywords=KEYWORDS,
        category="gpu",
        client_factories=client_factories,
    )

    logger.info("==================================================")
    logger.info("SPIDER DISCOVERY COMPLETE: %d new/updated SKUs registered in database.", len(discovered))
    for sku in discovered:
        logger.info(" - [%s] %s (%s) -> %s", sku.store_name.upper(), sku.product_title[:60], sku.search_keyword, sku.product_url)
    logger.info("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
