"""One-time migration: renames the database's Portuguese table/column names
to English, to match the code (src/db/schema.py and every repository were
already updated to the new names - see that commit for the full rationale:
the schema mixed Portuguese and English identifiers, e.g. `anuncio.loja_id`
next to `is_active`/`created_at`; translation belongs in the frontend i18n
layer, not the schema).

ALTER TABLE ... RENAME TO / RENAME COLUMN ... TO are metadata-only operations
in Postgres - no row is rewritten, no data is copied, and dependent foreign
keys keep working (Postgres tracks FKs by OID, not by name), so this is fast
and safe even against a live table with existing rows. Idempotent: skips any
table that's already been renamed (or never existed under the old name).

Run manually against each database you have: `python scripts/rename_pt_schema_to_en.py --dsn <dsn>`
"""
import argparse
import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings
from scripts.backup_db import backup_database

# (old_table, new_table, [(old_column, new_column), ...])
_TABLE_RENAMES: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("categoria", "categories", [("nome", "name"), ("criado_em", "created_at")]),
    ("marca", "brands", [("nome", "name"), ("criado_em", "created_at")]),
    ("produto", "products", [
        ("marca_id", "brand_id"), ("categoria_id", "category_id"),
        ("nome", "name"), ("criado_em", "created_at"),
    ]),
    ("loja", "stores", []),
    ("anuncio", "listings", [("loja_id", "store_id"), ("produto_id", "product_id")]),
    ("scraper_runs", "scraper_runs", [("loja_id", "store_id")]),
    ("listing_runs", "listing_runs", [("anuncio_id", "listing_id")]),
    ("coleta_preco", "price_observations", [("anuncio_id", "listing_id")]),
    ("trigger_requests", "trigger_requests", [("loja_id", "store_id")]),
    ("alert_rules", "alert_rules", [("loja_id", "store_id"), ("produto_id", "product_id")]),
    ("alert_events", "alert_events", [("coleta_preco_id", "price_observation_id")]),
]

# Old-named indexes that will be recreated under their new name by the next
# initialize_schema() call (main.py calls it on every boot) - just drop the
# stale ones here so they don't linger as dead duplicates.
_STALE_INDEXES = [
    "idx_produto_identity",
    "idx_scraper_runs_loja",
    "idx_listing_runs_anuncio",
    "idx_coleta_preco_anuncio",
    "idx_coleta_preco_run",
    "idx_anuncio_loja",
    "idx_produto_categoria",
]


async def _table_exists(conn, name: str) -> bool:
    return await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1)", name
    )


async def _column_exists(conn, table: str, column: str) -> bool:
    return await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_name = $1 AND column_name = $2)",
        table, column,
    )


async def rename_schema(dsn: str, apply: bool) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        renamed_tables = 0
        renamed_columns = 0

        for old_table, new_table, columns in _TABLE_RENAMES:
            table_now = old_table  # whichever name currently exists, before this step's rename
            if old_table != new_table:
                if await _table_exists(conn, old_table):
                    print(f"{'Renaming' if apply else 'Would rename'} table {old_table} -> {new_table}")
                    if apply:
                        await conn.execute(f'ALTER TABLE "{old_table}" RENAME TO "{new_table}"')
                        table_now = new_table
                    renamed_tables += 1
                elif await _table_exists(conn, new_table):
                    table_now = new_table
                else:
                    print(f"SKIP: neither {old_table} nor {new_table} exists - nothing to do.")
                    continue

            for old_col, new_col in columns:
                if await _column_exists(conn, table_now, old_col):
                    print(f"{'Renaming' if apply else 'Would rename'} column {new_table}.{old_col} -> {new_col}")
                    if apply:
                        await conn.execute(f'ALTER TABLE "{table_now}" RENAME COLUMN "{old_col}" TO "{new_col}"')
                    renamed_columns += 1

        if apply:
            for idx in _STALE_INDEXES:
                await conn.execute(f'DROP INDEX IF EXISTS "{idx}"')

        print(f"\n{'Renamed' if apply else 'Would rename'}: {renamed_tables} table(s), {renamed_columns} column(s).")
        if not apply:
            print("Dry run only - re-run with --apply to write these changes.")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually rename (default: dry run).")
    parser.add_argument("--dsn", default=None, help="Override settings.db_dsn.")
    args = parser.parse_args()
    dsn = args.dsn or settings.db_dsn
    print(f"Target database: {dsn}\n")

    if args.apply:
        backup_path = backup_database(dsn, keep=settings.backup_retention_count)
        if backup_path:
            print(f"Backed up database to {backup_path} before renaming.\n")
        else:
            print("WARNING: could not create a backup (pg_dump not found?) - proceeding anyway.\n")

    asyncio.run(rename_schema(dsn, apply=args.apply))


if __name__ == "__main__":
    main()
