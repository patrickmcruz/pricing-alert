import asyncio
import json
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.contract import StoreConfig, TargetUrlEntry
from src.core.browser import BrowserFactory
from src.core.execution import SKU_FAILURE_LABELS_PT, ScraperRunResult
from src.core.http_client import HTTPClientFactory
from src.core.config import settings
from src.core.logging_setup import configure_logging
from src.db.schema import connect, initialize_schema as initialize_db_schema
from src.engine.discovery import DiscoveryEngine
from src.engine.scheduler import PriceEngine
from src.engine.trigger_processor import TriggerProcessor
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository
from src.repositories.postgres_target_url_repository import PostgresTargetUrlRepository
from src.repositories.postgres_repository import PostgresPriceRepository
from src.repositories.postgres_execution_repository import PostgresExecutionRepository
from src.repositories.postgres_store_repository import PostgresStoreRepository
from src.repositories.postgres_trigger_repository import PostgresTriggerRepository
from src.core.registry import get_registered_scrapers
import src.scrapers  # noqa: F401 - importing the package triggers scraper self-registration
from src.alerts.postgres_alert_repository import PostgresAlertRepository
from src.alerts.dispatcher import AlertDispatcher
from src.alerts.channels.base import NotificationChannel
from src.alerts.channels.telegram import TelegramChannel
from apscheduler.triggers.cron import CronTrigger
from scripts.backup_db import backup_database

configure_logging(getattr(settings, "log_level", "INFO"), log_file=settings.log_file_path)
init_telemetry()

logger = logging.getLogger(__name__)

DB_DSN = settings.db_dsn


async def load_stores_config(store_repository) -> list[StoreConfig]:
    """Loads configuration and returns StoreConfig instances from the database-backed store registry."""
    stores = await store_repository.list_stores()

    registered_names = set(get_registered_scrapers().keys())
    configs = []
    for store in stores:
        if not store.is_active:
            continue
        if store.slug not in registered_names:
            logger.info("Skipping store '%s' because no scraper is registered for it.", store.slug)
            continue
        configs.append(
            StoreConfig(
                store_name=store.slug,
                target_keywords=settings.default_gpus,
                cron_times=settings.default_cron_times,
                enabled=True,
            )
        )
    return configs


def _log_multi_store_summary(results: list) -> None:
    """
    One boxed table across every store, instead of only the scattered
    per-store lines each run_scraper() call already logged - the "what
    actually happened" readout for a batched startup pass.
    """
    rows = [r for r in results if isinstance(r, ScraperRunResult)]
    if not rows:
        return

    name_width = max(len(r.store_name) for r in rows)
    lines = ["=" * 62, "  RESUMO DA EXECUÇÃO".ljust(62), "-" * 62]
    total_succeeded = 0
    total_skus = 0
    for r in rows:
        total_succeeded += r.listings_succeeded
        total_skus += r.listings_total
        icon = "✗" if r.error_message else ("○" if r.listings_total == 0 else ("✓" if r.listings_failed == 0 else "⚠"))
        counts = f"{r.listings_succeeded}/{r.listings_total} OK" if r.listings_total else "sem SKUs"
        detail = ""
        if r.error_message:
            detail = f"  ({r.error_message})"
        elif r.failure_breakdown:
            breakdown = ", ".join(
                f"{SKU_FAILURE_LABELS_PT.get(reason, reason)}={count}"
                for reason, count in r.failure_breakdown.items()
            )
            detail = f"  ({r.listings_failed} falharam: {breakdown})"
        lines.append(f"  {icon} {r.store_name.ljust(name_width)}  {counts}{detail}  ({r.duration_seconds:.1f}s)")
    lines.append("-" * 62)
    lines.append(f"  TOTAL: {total_succeeded}/{total_skus} SKUs OK em {len(rows)} loja(s)")
    lines.append("=" * 62)

    summary = "\n".join(lines)
    if any(r.error_message for r in rows):
        logger.error(summary)
    elif any(r.listings_failed for r in rows):
        logger.warning(summary)
    else:
        logger.info(summary)


async def _seed_stores(store_repository: PostgresStoreRepository) -> None:
    """
    Seeds the stores table from data/target-stores-list.json - the same file
    load_stores_config() reads - so every store referenced elsewhere resolves.
    Idempotent: get_or_create_store is a no-op for stores that already exist.
    """
    stores_file = settings.stores_config_path
    try:
        with open(stores_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Failed to load stores config from %s for seeding: %s", stores_file, e)
        return

    for store_key, store_info in data.items():
        await store_repository.get_or_create_store(
            slug=store_key,
            display_name=store_info["store_name"],
            base_url=store_info.get("base_url"),
        )


async def _seed_test_container_targets(target_url_repository) -> None:
    """Seeds a tiny, deterministic target-url set for container smoke tests."""
    if os.getenv("TEST_CONTAINER_MODE", "").lower() not in {"1", "true", "yes", "on"}:
        return

    logger.info("TEST_CONTAINER_MODE enabled; seeding a reduced SKU set for container smoke testing.")
    entries = [
        TargetUrlEntry(
            store_name="kabum",
            search_keyword="rtx 5070",
            product_url="https://www.kabum.com.br/produto/875474/placa-de-video-msi-rtx-5070-12gb-gddr7-192-bits-shadow-2x-oc-912-v532-011",
            brand="MSI",
            model="Shadow 2X OC",
            product_title="Placa de vídeo MSI RTX 5070 12GB",
        ),
        TargetUrlEntry(
            store_name="kabum",
            search_keyword="rtx 5070",
            product_url="https://www.kabum.com.br/produto/725587/placa-de-video-msi-geforce-rtx-5070-12g-ventus-2x-oc-12-gb-gddr7-28gbps-nvidia-geforce-rtx-5070-g5070-12v2c",
            brand="MSI",
            model="Ventus 2X OC",
            product_title="Placa de vídeo MSI RTX 5070 Ventus 2X",
        ),
        TargetUrlEntry(
            store_name="kabum",
            search_keyword="rtx 5070 ti",
            product_url="https://www.kabum.com.br/produto/857022/placa-de-video-nvidia-geforce-msi-rtx5070ti-16gb-gddr7-256its-shadow-3x-oc-912-v531-097",
            brand="MSI",
            model="Shadow 3X OC",
            product_title="Placa de vídeo MSI RTX 5070 Ti",
        ),
        TargetUrlEntry(
            store_name="kabum",
            search_keyword="rtx 5070 ti",
            product_url="https://www.kabum.com.br/produto/996236/placa-de-video-gainward-rtx-5070-ti-phoenix-16gb-gddr7",
            brand="Gainward",
            model="Phoenix",
            product_title="Placa de vídeo Gainward RTX 5070 Ti",
        ),
        TargetUrlEntry(
            store_name="pichau",
            search_keyword="rtx 5070",
            product_url="https://www.pichau.com.br/placa-de-video-asus-geforce-rtx-5070-12gb-gddr7-192-bit-dual-rtx5070-12g",
            brand="ASUS",
            model="Dual 12GB",
            product_title="Placa de vídeo ASUS RTX 5070 Dual",
        ),
        TargetUrlEntry(
            store_name="pichau",
            search_keyword="rtx 5070",
            product_url="https://www.pichau.com.br/placa-de-video-asus-geforce-rtx-5070-prime-oc-edition-12gb-gddr7-192-bit-prime-rtx5070-o12g",
            brand="ASUS",
            model="Prime OC",
            product_title="Placa de vídeo ASUS RTX 5070 Prime",
        ),
        TargetUrlEntry(
            store_name="pichau",
            search_keyword="rtx 5070 ti",
            product_url="https://www.pichau.com.br/placa-de-video-asus-geforce-rtx-5070-ti-prime-16gb-gddr7-256-bit-prime-rtx5070ti-16g-nac",
            brand="ASUS",
            model="Prime 16GB",
            product_title="Placa de vídeo ASUS RTX 5070 Ti Prime",
        ),
        TargetUrlEntry(
            store_name="pichau",
            search_keyword="rtx 5070 ti",
            product_url="https://www.pichau.com.br/placa-de-video-asus-geforce-rtx-5070-ti-16gb-gddr7-256-bit-prime-rtx5070ti-16g",
            brand="ASUS",
            model="Prime 16GB",
            product_title="Placa de vídeo ASUS RTX 5070 Ti",
        ),
        TargetUrlEntry(
            store_name="terabyte",
            search_keyword="rtx 5070",
            product_url="https://www.terabyteshop.com.br/produto/34699/placa-de-video-inno3d-nvidia-geforce-rtx-5070-twin-x2-oc-12gb-gddr7-dlss-ray-tracing-n50702-12d7x-195064n",
            brand="Inno3D",
            model="Twin X2 OC",
            product_title="Placa de vídeo Inno3D RTX 5070",
        ),
        TargetUrlEntry(
            store_name="terabyte",
            search_keyword="rtx 5070",
            product_url="https://www.terabyteshop.com.br/produto/34705/placa-de-video-inno3d-nvidia-geforce-rtx-5070-twin-x2-12gb-gddr7-dlss-ray-tracing-n50702-12d7-195064n",
            brand="Inno3D",
            model="Twin X2",
            product_title="Placa de vídeo Inno3D RTX 5070 Twin X2",
        ),
        TargetUrlEntry(
            store_name="terabyte",
            search_keyword="rtx 5070 ti",
            product_url="https://www.terabyteshop.com.br/produto/34579/placa-de-video-asus-prime-nvidia-geforce-rtx-5070-ti-oc-edition-16gb-gddr7-dlss-ray-tracing-prime-rtx5070ti-o16g",
            brand="ASUS",
            model="Prime OC",
            product_title="Placa de vídeo ASUS RTX 5070 Ti Prime",
        ),
        TargetUrlEntry(
            store_name="terabyte",
            search_keyword="rtx 5070 ti",
            product_url="https://www.terabyteshop.com.br/produto/34580/placa-de-video-asus-tuf-gaming-nvidia-geforce-rtx-5070-ti-oc-edition-16gb-gddr7-dlss-ray-tracing-tuf-rtx5070ti-o16g-gaming",
            brand="ASUS",
            model="TUF Gaming OC",
            product_title="Placa de vídeo ASUS RTX 5070 Ti TUF",
        ),
    ]

    async with connect(DB_DSN) as db:
        await db.execute("TRUNCATE TABLE price_observations RESTART IDENTITY CASCADE")
        await db.execute("TRUNCATE TABLE listings RESTART IDENTITY CASCADE")
        await db.execute("TRUNCATE TABLE target_urls RESTART IDENTITY CASCADE")

    await target_url_repository.upsert_many(entries)


async def startup_routine(engine: PriceEngine):
    """Runs immediately on startup to update graphs for the user."""
    logger.info("Executing immediate startup routine (Scrapers)...")

    # Run all scrapers concurrently against the SKUs already tracked in the DB
    # (added/edited/removed via the "Gerenciar GPUs" dashboard page - see
    # scripts/migrate_target_urls.py for one-time seeding from the legacy
    # data/target_urls.json manifest).
    tasks = [engine.run_scraper(scraper) for scraper in engine.scrapers.values()]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for res in results:
        if isinstance(res, Exception):
            logger.error("A scraper failed during startup: %s", res, exc_info=res)

    _log_multi_store_summary(results)
    logger.info("Startup routine complete. Initial data populated.")


async def main():
    logger.info("Initializing GPU Price Tracker Orchestrator...")

    # 0. Snapshot the DB before touching it - cheap insurance against any
    # mistake in this boot sequence or a subsequent manual script/migration.
    # Shells out to pg_dump, so it's safe even against a live db.
    backup_path = backup_database(DB_DSN, keep=settings.backup_retention_count)
    if backup_path:
        logger.info("Pre-boot DB backup created: %s", backup_path)

    # 1. Initialize Persistence Layer - single shared schema, applied once
    # before any repository touches the DB.
    await initialize_db_schema(DB_DSN)

    repository = PostgresPriceRepository(dsn=DB_DSN)
    alert_repository = PostgresAlertRepository(dsn=DB_DSN)
    execution_repository = PostgresExecutionRepository(dsn=DB_DSN)
    trigger_repository = PostgresTriggerRepository(dsn=DB_DSN)
    store_repository = PostgresStoreRepository(dsn=DB_DSN)

    # Seed the stores table from the same JSON manifest load_stores_config()
    # already reads, so every store referenced by scraper_runs/anuncio/
    # trigger_requests/alert_rules resolves to a real row.
    await _seed_stores(store_repository)

    # Re-assert the full target_urls manifest (src/db/schema.py - see
    # specs/target-urls-table/spec.md) as active on every boot - save_skus()
    # is an upsert (ON CONFLICT ... is_active = true), so this is idempotent
    # and safe to run every time, not just once. This is what guarantees
    # `docker compose up` always brings up the complete SKU set in
    # production, independent of whatever a local APP_ENV=develop session
    # has trimmed in its own separate pricing_dev database (see
    # scripts/trim_dev_listings.py) - this container is always
    # APP_ENV=production (Dockerfile.orchestrator), so it can never run
    # against pricing_dev in the first place.
    if settings.env == "production":
        catalog_repository = PostgresCatalogRepository(dsn=DB_DSN)
        target_url_repository = PostgresTargetUrlRepository(dsn=DB_DSN)
        await _seed_test_container_targets(target_url_repository)
        discovery_engine = DiscoveryEngine(
            repository=repository, catalog_repository=catalog_repository, target_url_repository=target_url_repository
        )
        await discovery_engine.run_discovery(configs=[])

        # Configurable SKU cap from config.toml (max_skus_per_chipset) or env var (MAX_URLS_PER_CHIPSET)
        max_skus_cap = settings.max_skus_per_chipset or (int(os.getenv("MAX_URLS_PER_CHIPSET")) if os.getenv("MAX_URLS_PER_CHIPSET") else 0)
        if max_skus_cap > 0:
            try:
                from scripts.trim_dev_listings import trim_dev_listings
                logger.info("Config mode active: Capping active listings to %d per (store, chipset)...", max_skus_cap)
                trim_dev_listings(DB_DSN, keep=max_skus_cap, allow_production=True)
            except Exception as e:
                logger.warning("Failed to apply max_skus_per_chipset cap: %s", e)

    # Same rationale as fail_stale_processing below: a "running" row can only
    # be legitimate if this process is still alive, so after a restart it's
    # provably orphaned - left alone it shows as running forever on the
    # Execuções dashboard page.
    await execution_repository.fail_stale_running_runs("Orphaned: orchestrator restarted while running")
    await execution_repository.fail_stale_running_sku_runs("Orphaned: orchestrator restarted while running")

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

    # Explicit timezone as the scheduler's own default (used for anything
    # that doesn't set its own, e.g. jobs added without a trigger timezone).
    # This alone does NOT make individual CronTrigger instances São
    # Paulo-aware - each one resolves its own tz independently unless told
    # otherwise (see the timezone= passed explicitly in build_schedule and
    # to the daily backup job below).
    scheduler = AsyncIOScheduler(timezone=settings.display_timezone)
    engine = PriceEngine(
        scheduler=scheduler,
        repository=repository,
        client_factories=client_factories,
        on_price_saved=dispatcher.handle_price,
        execution_repository=execution_repository,
    )
    trigger_processor = TriggerProcessor(trigger_repository=trigger_repository, engine=engine)

    # 4. Register Concrete Scrapers (auto-discovered via @register_scraper)
    engine.register_scrapers(get_registered_scrapers().values())

    # 5. Build Schedule
    configs = await load_stores_config(store_repository)
    engine.build_schedule(configs)

    # Daily DB backup, independent of the boot-time one above - covers
    # long-running deployments that don't restart often.
    # timezone= is required here too - CronTrigger resolves its own tz via
    # tzlocal (the container's UTC system clock) unless told otherwise, it
    # does not inherit the scheduler's own timezone (see src/engine/scheduler.py).
    scheduler.add_job(
        lambda: backup_database(DB_DSN, keep=settings.backup_retention_count),
        trigger=CronTrigger(
            hour=settings.backup_cron_hour,
            minute=settings.backup_cron_minute,
            timezone=settings.display_timezone,
        ),
        id="daily_db_backup",
        replace_existing=True,
    )

    # 6. Start Orchestration
    engine.start()

    logger.info("Orchestrator cron schedule started.")

    # Start polling for "run now" requests concurrently with the startup scrape
    # below, not after it - startup_routine can take minutes (every store's
    # SKUs, sequentially, with jitter between each), and awaiting it first would
    # silently ignore any dashboard trigger created during that whole window.
    trigger_task = asyncio.create_task(trigger_processor.run_forever())

    # 7. Run initial scrape against the SKUs already tracked in the DB
    await startup_routine(engine)

    logger.info("Orchestrator running. Press Ctrl+C to exit.")

    # trigger_task never returns on its own - this keeps the event loop alive
    # for the rest of the process lifetime, same as before.
    await trigger_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down Orchestrator...")
