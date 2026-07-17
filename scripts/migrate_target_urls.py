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
from src.db.schema import initialize_schema as initialize_db_schema
from src.engine.discovery import DiscoveryEngine
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository
from src.repositories.postgres_repository import PostgresPriceRepository
from scripts.backup_db import backup_database


async def migrate():
    backup_path = backup_database(settings.db_dsn, keep=settings.backup_retention_count)
    if backup_path:
        print(f"Backed up the database to {backup_path} before migrating.")

    print("Migrating data/target_urls.json into the database ...")
    await initialize_db_schema(settings.db_dsn)
    repo = PostgresPriceRepository(dsn=settings.db_dsn)
    catalog_repo = PostgresCatalogRepository(dsn=settings.db_dsn)

    engine = DiscoveryEngine(repository=repo, catalog_repository=catalog_repo)  # defaults to data/target_urls.json
    await engine.run_discovery(configs=[])

    skus = await repo.list_all_skus()
    marcas = await catalog_repo.list_marcas()
    categorias = await catalog_repo.list_categorias()
    print(
        f"Done. {len(skus)} SKU(s) now tracked in the database "
        f"({len(marcas)} marca(s), {len(categorias)} categoria(s) in the catalog)."
    )


if __name__ == "__main__":
    asyncio.run(migrate())
