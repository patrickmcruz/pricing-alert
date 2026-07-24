import asyncio
import logging
import os
import sys
import httpx

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings
from src.core.contract import TargetUrlEntry
from src.spiders.mercadolivre import MercadoLivreSpider
from src.repositories.postgres_repository import PostgresPriceRepository
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository
from src.repositories.postgres_target_url_repository import PostgresTargetUrlRepository
from src.engine.discovery import DiscoveryEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main():
    logger.info("Connecting to database DSN: %s", settings.db_dsn)
    logger.info("Starting Mercado Livre Spider Discovery for keywords: %s", settings.default_gpus)

    spider = MercadoLivreSpider()
    discovered_skus = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for kw in settings.default_gpus:
            logger.info("Running Mercado Livre spider for keyword '%s'...", kw)
            skus = await spider.execute(kw, category="gpu", client=client)
            logger.info("Keyword '%s' -> Discovered %d SKU(s) in Mercado Livre", kw, len(skus))
            for sku in skus:
                logger.info("  - %s -> %s", sku.product_title, sku.product_url)
            discovered_skus.extend(skus)

    if not discovered_skus:
        logger.warning("No Mercado Livre SKUs discovered.")
        return

    # Convert DiscoveredSKU to TargetUrlEntry and save to database
    entries = []
    for d_sku in discovered_skus:
        entry = TargetUrlEntry(
            store_name=d_sku.store_name,
            search_keyword=d_sku.search_keyword,
            product_url=d_sku.product_url,
            brand=None,
            model=None,
            product_title=d_sku.product_title,
        )
        entries.append(entry)

    target_url_repo = PostgresTargetUrlRepository(dsn=settings.db_dsn)
    await target_url_repo.upsert_many(entries)
    logger.info("Successfully upserted %d Mercado Livre SKUs into target_urls (%s)!", len(entries), settings.db_dsn)

    price_repo = PostgresPriceRepository(dsn=settings.db_dsn)
    catalog_repo = PostgresCatalogRepository(dsn=settings.db_dsn)
    discovery_engine = DiscoveryEngine(
        repository=price_repo,
        catalog_repository=catalog_repo,
        target_url_repository=target_url_repo,
    )
    await discovery_engine.run_discovery(configs=[])
    logger.info("Mercado Livre SKUs persisted to listings table in PostgreSQL (%s)!", settings.db_dsn)

    # Also sync to production database 'pricing' if running on host in develop mode
    prod_dsn = "postgresql://pricing:pricing@localhost:5432/pricing"
    if settings.db_dsn != prod_dsn:
        try:
            prod_target_repo = PostgresTargetUrlRepository(dsn=prod_dsn)
            await prod_target_repo.upsert_many(entries)
            prod_price_repo = PostgresPriceRepository(dsn=prod_dsn)
            prod_catalog_repo = PostgresCatalogRepository(dsn=prod_dsn)
            prod_discovery = DiscoveryEngine(
                repository=prod_price_repo,
                catalog_repository=prod_catalog_repo,
                target_url_repository=prod_target_repo,
            )
            await prod_discovery.run_discovery(configs=[])
            logger.info("Successfully synced Mercado Livre SKUs to production database (%s)!", prod_dsn)
        except Exception as e:
            logger.warning("Could not sync to production database: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
