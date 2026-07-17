"""One-time migration: copies every row out of the legacy SQLite database
(stores/brands/chipsets/gpu_models/store_listings/scraper_runs/listing_runs/
price_observations/alert_rules/alert_events) into the new PostgreSQL schema
(stores/brands/categories/products/listings/scraper_runs/listing_runs/
price_observations/alert_rules/alert_events).

Every brand+chipset+gpu_model row becomes a product under a single "GPU"
category, with the chipset folded into products.specs (chipset/chip_maker) -
see src/core/catalog.py for why chipset no longer has its own table.

Existing UUIDs are preserved (not regenerated), so every FK stays consistent
across the copy. Runs inside a single Postgres transaction - either every row
lands, or none does.

Run manually once: `python scripts/migrate_sqlite_to_postgres.py path/to/legacy.db`
(defaults to whatever settings.db_path used to point at, if you still have
that file around - pass the path explicitly if config.toml has already been
updated to Postgres-only settings).
"""
import asyncio
import json
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings
from src.core.catalog import GPU_CATEGORY_SLUG
from src.db.schema import initialize_schema
from scripts.backup_db import backup_database


def _rows(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(f"SELECT * FROM {table}").fetchall()


async def migrate(sqlite_path: str, dsn: str) -> None:
    import asyncpg

    if not os.path.exists(sqlite_path):
        raise SystemExit(f"SQLite database not found at {sqlite_path!r}.")

    backup_path = backup_database(dsn, keep=settings.backup_retention_count)
    if backup_path:
        print(f"Backed up destination database to {backup_path} before migrating.")

    await initialize_schema(dsn)

    sqlite_conn = sqlite3.connect(sqlite_path)
    pg = await asyncpg.connect(dsn)
    try:
        await pg.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
        async with pg.transaction():
            # 1. stores
            for r in _rows(sqlite_conn, "stores"):
                await pg.execute(
                    "INSERT INTO stores (id, slug, display_name, base_url, is_active, created_at) "
                    "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (id) DO NOTHING",
                    r["id"], r["slug"], r["display_name"], r["base_url"],
                    bool(r["is_active"]), r["created_at"],
                )
            print(f"Migrated {len(_rows(sqlite_conn, 'stores'))} stores row(s).")

            # 2. categories: a single synthetic "GPU" row every legacy gpu_models row hangs off.
            gpu_category_id = "00000000-0000-0000-0000-000000000001"
            await pg.execute(
                "INSERT INTO categories (id, name, slug, parent_id, created_at) "
                "VALUES ($1, 'GPU', $2, NULL, now()) ON CONFLICT (id) DO NOTHING",
                gpu_category_id, GPU_CATEGORY_SLUG,
            )

            # 3. brands
            for r in _rows(sqlite_conn, "brands"):
                await pg.execute(
                    "INSERT INTO brands (id, name, created_at) VALUES ($1, $2, $3) ON CONFLICT (id) DO NOTHING",
                    r["id"], r["name"], r["created_at"],
                )
            print(f"Migrated {len(_rows(sqlite_conn, 'brands'))} brands row(s).")

            # 4. products (was chipsets + gpu_models combined, chipset folded into specs)
            chipsets_by_id = {r["id"]: r for r in _rows(sqlite_conn, "chipsets")}
            gpu_models = _rows(sqlite_conn, "gpu_models")
            for r in gpu_models:
                chipset = chipsets_by_id.get(r["chipset_id"])
                specs = {
                    "chipset": chipset["name"] if chipset else None,
                    "chip_maker": chipset["chip_maker"] if chipset else "UNKNOWN",
                }
                await pg.execute(
                    "INSERT INTO products (id, brand_id, category_id, name, gtin, specs, created_at) "
                    "VALUES ($1, $2, $3, $4, NULL, $5, $6) ON CONFLICT (id) DO NOTHING",
                    r["id"], r["brand_id"], gpu_category_id, r["model_name"], specs, r["created_at"],
                )
            print(f"Migrated {len(gpu_models)} products row(s) (from gpu_models x chipsets).")

            # 5. listings (was store_listings)
            for r in _rows(sqlite_conn, "store_listings"):
                await pg.execute(
                    """
                    INSERT INTO listings (id, store_id, product_id, product_url, product_title,
                        search_keyword, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT (id) DO NOTHING
                    """,
                    r["id"], r["store_id"], r["gpu_model_id"], r["product_url"], r["product_title"],
                    r["search_keyword"], bool(r["is_active"]), r["created_at"], r["updated_at"],
                )
            print(f"Migrated {len(_rows(sqlite_conn, 'store_listings'))} listings row(s).")

            # 6. scraper_runs (column names unchanged)
            for r in _rows(sqlite_conn, "scraper_runs"):
                await pg.execute(
                    """
                    INSERT INTO scraper_runs (id, store_id, status, started_at, finished_at,
                        listings_total, listings_succeeded, listings_failed, error_message)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT (id) DO NOTHING
                    """,
                    r["id"], r["store_id"], r["status"], r["started_at"], r["finished_at"],
                    r["listings_total"], r["listings_succeeded"], r["listings_failed"], r["error_message"],
                )
            print(f"Migrated {len(_rows(sqlite_conn, 'scraper_runs'))} scraper_runs row(s).")

            # 7. listing_runs (FK rename: store_listing_id -> listing_id)
            for r in _rows(sqlite_conn, "listing_runs"):
                await pg.execute(
                    """
                    INSERT INTO listing_runs (id, scraper_run_id, listing_id, product_url, product_title,
                        status, started_at, finished_at, error_message)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT (id) DO NOTHING
                    """,
                    r["id"], r["scraper_run_id"], r["store_listing_id"], r["product_url"], r["product_title"],
                    r["status"], r["started_at"], r["finished_at"], r["error_message"],
                )
            print(f"Migrated {len(_rows(sqlite_conn, 'listing_runs'))} listing_runs row(s).")

            # 8. price_observations (FK rename: store_listing_id -> listing_id)
            for r in _rows(sqlite_conn, "price_observations"):
                await pg.execute(
                    """
                    INSERT INTO price_observations (id, listing_id, scraper_run_id, price_cash, price_installments,
                        installment_count, currency, discount, is_available, parser_version, scraped_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) ON CONFLICT (id) DO NOTHING
                    """,
                    r["id"], r["store_listing_id"], r["scraper_run_id"], r["price_cash"],
                    r["price_installments"], r["installment_count"], r["currency"], r["discount"],
                    bool(r["is_available"]), r["parser_version"], r["scraped_at"],
                )
            print(f"Migrated {len(_rows(sqlite_conn, 'price_observations'))} price_observations row(s).")

            # 9. alert_rules (FK renames: store_id unchanged, gpu_model_id -> product_id)
            for r in _rows(sqlite_conn, "alert_rules"):
                await pg.execute(
                    """
                    INSERT INTO alert_rules (id, store_id, product_id, search_keyword,
                        threshold_type, threshold_value, is_active, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (id) DO NOTHING
                    """,
                    r["id"], r["store_id"], r["gpu_model_id"], r["search_keyword"],
                    r["threshold_type"], r["threshold_value"], bool(r["is_active"]), r["created_at"],
                )
            print(f"Migrated {len(_rows(sqlite_conn, 'alert_rules'))} alert_rules row(s).")

            # 10. alert_events (id becomes a fresh BIGSERIAL - old TEXT ids aren't preserved)
            for r in _rows(sqlite_conn, "alert_events"):
                await pg.execute(
                    """
                    INSERT INTO alert_events (alert_rule_id, price_observation_id, reason, triggered_at)
                    VALUES ($1, $2, $3, $4)
                    """,
                    r["alert_rule_id"], r["price_observation_id"], r["reason"], r["triggered_at"],
                )
            print(f"Migrated {len(_rows(sqlite_conn, 'alert_events'))} alert_events row(s).")

        print("\nMigration complete. Verify row counts against the source before deleting the SQLite file.")
    finally:
        sqlite_conn.close()
        await pg.close()


if __name__ == "__main__":
    sqlite_arg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJECT_ROOT, "data", "prices.db")
    asyncio.run(migrate(sqlite_arg, settings.db_dsn))
