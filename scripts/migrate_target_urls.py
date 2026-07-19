"""One-time migration: import data/target_urls.json into the target_urls DB
table (src/db/schema.py - see specs/target-urls-table/spec.md), then run
discovery from that table to resolve/create the Brand/Categoria/Produto
catalog entries every row needs and upsert the corresponding `listings` rows.

Run manually once (`python scripts/migrate_target_urls.py`) to cut over from
the legacy JSON manifest. Safe to run again later too: importing is
`ON CONFLICT (product_url) DO NOTHING` (existing rows are left alone) and
discovery's downstream catalog/listings resolution is already idempotent
(it also backfills any existing listings row missing a produto_id - see
DiscoveryEngine._backfill_existing_rows).

From then on, GPUs are added/edited/removed via the "Gerenciar GPUs"
dashboard page, and new discovery scripts write straight into target_urls
(see scripts/discover_pichau_gpus.py) - main.py never reads the JSON file,
so this script is the only remaining consumer of it, and only for as long
as it still exists on disk.
"""
import asyncio
import os
import sys
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings
from src.core.contract import TargetUrlEntry
from src.db.schema import initialize_schema as initialize_db_schema
from src.engine.discovery import DiscoveryEngine
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository
from src.repositories.postgres_repository import PostgresPriceRepository
from src.repositories.postgres_target_url_repository import PostgresTargetUrlRepository
from scripts.backup_db import backup_database


def _load_json_manifest() -> list[TargetUrlEntry]:
    if not os.path.exists(settings.target_urls_path):
        print(f"{settings.target_urls_path} not found - nothing to import (already migrated?).")
        return []
    with open(settings.target_urls_path, "r", encoding="utf-8") as f:
        rows = json.load(f)
    return [
        TargetUrlEntry(
            store_name=row["store_name"],
            search_keyword=row["search_keyword"],
            product_url=row["product_url"],
            brand=row.get("brand"),
            model=row.get("model"),
            product_title=row.get("product_title"),
        )
        for row in rows
    ]


async def migrate():
    backup_path = backup_database(settings.db_dsn, keep=settings.backup_retention_count)
    if backup_path:
        print(f"Backed up the database to {backup_path} before migrating.")

    await initialize_db_schema(settings.db_dsn)
    repo = PostgresPriceRepository(dsn=settings.db_dsn)
    catalog_repo = PostgresCatalogRepository(dsn=settings.db_dsn)
    target_url_repo = PostgresTargetUrlRepository(dsn=settings.db_dsn)

    entries = _load_json_manifest()
    if entries:
        inserted = await target_url_repo.upsert_many(entries)
        print(f"Imported {inserted} new row(s) from {settings.target_urls_path} into target_urls "
              f"({len(entries) - inserted} already present).")

    print("Running discovery from target_urls ...")
    engine = DiscoveryEngine(repository=repo, catalog_repository=catalog_repo, target_url_repository=target_url_repo)
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
