"""One-time migration: import data/target_urls.json into the target_urls DB table,
and resolve/create the Brand/GpuChipset/GpuModel catalog entries every row needs.

Run manually once (`python scripts/migrate_target_urls.py`) after upgrading to
DB-managed GPU tracking, and again any time you upgrade a DB that predates the
gpu_model_id catalog (it also backfills any existing target_urls row missing
one - see DiscoveryEngine._backfill_existing_rows). Idempotent either way.

From then on, GPUs are added/edited/removed via the "Gerenciar GPUs" dashboard
page - main.py no longer re-reads the JSON file on every boot, so this script
is the only remaining consumer of it.
"""
import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings
from src.engine.discovery import DiscoveryEngine
from src.repositories.sqlite_catalog_repository import SQLiteCatalogRepository
from src.repositories.sqlite_repository import SQLitePriceRepository


async def migrate():
    print(f"Migrating data/target_urls.json into {settings.db_path} ...")
    repo = SQLitePriceRepository(db_path=settings.db_path)
    await repo.initialize_schema()
    catalog_repo = SQLiteCatalogRepository(db_path=settings.db_path)
    await catalog_repo.initialize_schema()

    engine = DiscoveryEngine(repository=repo, catalog_repository=catalog_repo)  # defaults to data/target_urls.json
    await engine.run_discovery(configs=[])

    skus = await repo.list_all_skus()
    brands = await catalog_repo.list_brands()
    chipsets = await catalog_repo.list_chipsets()
    print(
        f"Done. {len(skus)} SKU(s) now tracked in the database "
        f"({len(brands)} brand(s), {len(chipsets)} chipset(s) in the catalog)."
    )


if __name__ == "__main__":
    asyncio.run(migrate())
