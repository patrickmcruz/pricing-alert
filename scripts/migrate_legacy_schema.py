"""One-shot migration: rewrites an existing data/prices.db-style file (written
under the OLD ad-hoc table names/shapes: prices, target_urls, gpu_chipsets,
sku_runs, alert_history, and pre-normalization scraper_runs/alert_rules/
trigger_requests) into the new normalized schema (src/db/schema.py), IN PLACE
in the same db file.

Run manually (`python scripts/migrate_legacy_schema.py [db_path]`) against a
COPY of your DB first. This script is idempotent: running it against a DB
that's already been migrated (or a fresh one with no legacy tables at all) is
a safe no-op.

It does NOT drop the old tables - it prints DROP TABLE statements for you to
run by hand once you've verified the migration looks right.
"""
import asyncio
import json
import os
import sqlite3
import sys
from typing import Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings
from src.db.schema import initialize_schema as initialize_db_schema
from scripts.backup_db import backup_database

# Tables whose *names* are reused by the new schema but whose column shapes
# changed - these must be renamed out of the way before initialize_schema()
# freely creates fresh ones under the original names. brands/gpu_models keep
# their old names too (only gpu_chipsets was renamed to chipsets), but gained
# a NOT NULL created_at column (brands) / model_name instead of variant_name
# (gpu_models), so they need the same treatment.
_RENAME_TO_LEGACY = {
    "scraper_runs": "legacy_scraper_runs",
    "alert_rules": "legacy_alert_rules",
    "trigger_requests": "legacy_trigger_requests",
    "brands": "legacy_brands",
    "gpu_models": "legacy_gpu_models",
}

STORES_JSON_PATH = os.path.join(PROJECT_ROOT, "data", "target-stores-list.json")


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (name,)
    )
    return cur.fetchone() is not None


def _row_count(conn: sqlite3.Connection, name: str) -> int:
    if not _table_exists(conn, name):
        return 0
    return conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]


def _already_migrated(conn: sqlite3.Connection) -> bool:
    """
    Migration is considered already-done (or unnecessary) if the new schema's
    core tables exist and have data, OR if the legacy tables this script reads
    from don't exist at all (fresh/in-memory DB).
    """
    has_new_data = _table_exists(conn, "store_listings") and _row_count(conn, "store_listings") > 0
    has_legacy_source = _table_exists(conn, "prices") or _table_exists(conn, "target_urls")
    if has_new_data:
        return True
    if not has_legacy_source:
        return True
    return False


def _rename_reused_tables(conn: sqlite3.Connection) -> None:
    for old_name, legacy_name in _RENAME_TO_LEGACY.items():
        if _table_exists(conn, old_name) and not _table_exists(conn, legacy_name):
            conn.execute(f"ALTER TABLE {old_name} RENAME TO {legacy_name}")


def _seed_stores(conn: sqlite3.Connection) -> None:
    now = "datetime('now')"
    try:
        with open(STORES_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"WARNING: could not load {STORES_JSON_PATH}: {e}")
        data = {}

    for slug, info in data.items():
        conn.execute(
            f"""
            INSERT OR IGNORE INTO stores (id, slug, display_name, base_url, is_active, created_at)
            VALUES (lower(hex(randomblob(16))), ?, ?, ?, 1, {now})
            """,
            (slug, info.get("store_name", slug), info.get("base_url")),
        )

    # Any store_name referenced by legacy tables but missing from the JSON
    # manifest (e.g. a store that was later removed from config) still needs
    # a stores row so store_listings/scraper_runs can resolve a store_id.
    legacy_names = set()
    for table, col in (("target_urls", "store_name"), ("prices", "store_name")):
        if _table_exists(conn, table):
            legacy_names.update(
                r[0] for r in conn.execute(f"SELECT DISTINCT {col} FROM {table}").fetchall()
            )
    for name in legacy_names:
        conn.execute(
            f"""
            INSERT OR IGNORE INTO stores (id, slug, display_name, base_url, is_active, created_at)
            VALUES (lower(hex(randomblob(16))), ?, ?, NULL, 1, {now})
            """,
            (name, name),
        )


def _migrate_brands_chipsets_gpu_models(conn: sqlite3.Connection) -> None:
    if _table_exists(conn, "legacy_brands"):
        for row in conn.execute("SELECT id, name FROM legacy_brands").fetchall():
            conn.execute(
                "INSERT OR IGNORE INTO brands (id, name, created_at) VALUES (?, ?, datetime('now'))",
                row,
            )

    if _table_exists(conn, "gpu_chipsets"):
        for row in conn.execute("SELECT id, name, chip_maker FROM gpu_chipsets").fetchall():
            conn.execute(
                """
                INSERT OR IGNORE INTO chipsets (id, name, chip_maker, created_at)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (row[0], row[1], row[2] or "UNKNOWN"),
            )

    if _table_exists(conn, "legacy_gpu_models"):
        cols = [r[1] for r in conn.execute("PRAGMA table_info(legacy_gpu_models)").fetchall()]
        name_col = "variant_name" if "variant_name" in cols else "model_name"
        for row in conn.execute(
            f"SELECT id, brand_id, chipset_id, {name_col} FROM legacy_gpu_models"
        ).fetchall():
            conn.execute(
                """
                INSERT OR IGNORE INTO gpu_models (id, brand_id, chipset_id, model_name, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                row,
            )


def _migrate_store_listings(conn: sqlite3.Connection) -> tuple[int, int]:
    if not _table_exists(conn, "target_urls"):
        return 0, 0

    rows = conn.execute(
        "SELECT product_url, store_name, search_keyword, gpu_model_id, product_title FROM target_urls"
    ).fetchall()

    migrated = 0
    skipped = 0
    for product_url, store_name, search_keyword, gpu_model_id, product_title in rows:
        if gpu_model_id is None:
            skipped += 1
            continue
        store_row = conn.execute(
            "SELECT id FROM stores WHERE slug = ?", (store_name,)
        ).fetchone()
        if not store_row:
            skipped += 1
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO store_listings
                (id, store_id, gpu_model_id, product_url, product_title, search_keyword,
                 is_active, created_at, updated_at)
            VALUES (lower(hex(randomblob(16))), ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))
            """,
            (store_row[0], gpu_model_id, product_url, product_title, search_keyword),
        )
        migrated += 1

    if skipped:
        print(f"Skipped {skipped} legacy target_urls row(s) missing a resolved gpu_model_id.")
    return migrated, skipped


def _resolve_or_create_orphan_listing(
    conn: sqlite3.Connection, product_url: str, store_name: Optional[str], product_title: Optional[str]
) -> Optional[str]:
    """
    Looks up store_listings.id by product_url; if missing (the SKU was later
    deleted from target_urls), tries to synthesize a soft-deleted listing row
    so listing_runs/price_observations history isn't silently orphaned.
    Returns None (caller should skip) if no gpu_model_id can be found anywhere.
    """
    row = conn.execute("SELECT id FROM store_listings WHERE product_url = ?", (product_url,)).fetchone()
    if row:
        return row[0]

    if not store_name:
        return None

    store_row = conn.execute("SELECT id FROM stores WHERE slug = ?", (store_name,)).fetchone()
    if not store_row:
        return None

    # No gpu_model_id can be recovered for a row that was never in target_urls
    # (or was deleted before this migration ran) - without one, store_listings
    # can't accept the row (gpu_model_id is NOT NULL). Skip it.
    return None


def _migrate_scraper_runs(conn: sqlite3.Connection) -> tuple[int, int]:
    if not _table_exists(conn, "legacy_scraper_runs"):
        return 0, 0

    rows = conn.execute(
        "SELECT run_id, store_name, status, started_at, finished_at, "
        "skus_total, skus_succeeded, skus_failed, error_message FROM legacy_scraper_runs"
    ).fetchall()

    migrated = 0
    skipped = 0
    for (run_id, store_name, status, started_at, finished_at,
         skus_total, skus_succeeded, skus_failed, error_message) in rows:
        store_row = conn.execute("SELECT id FROM stores WHERE slug = ?", (store_name,)).fetchone()
        if not store_row:
            skipped += 1
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO scraper_runs
                (id, store_id, status, started_at, finished_at,
                 listings_total, listings_succeeded, listings_failed, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, store_row[0], status, started_at, finished_at,
             skus_total or 0, skus_succeeded or 0, skus_failed or 0, error_message),
        )
        migrated += 1
    return migrated, skipped


def _migrate_listing_runs(conn: sqlite3.Connection) -> tuple[int, int]:
    if not _table_exists(conn, "sku_runs"):
        return 0, 0

    rows = conn.execute(
        "SELECT sku_run_id, run_id, store_name, product_url, product_title, status, "
        "started_at, finished_at, error_message FROM sku_runs"
    ).fetchall()

    migrated = 0
    skipped = 0
    for (sku_run_id, run_id, store_name, product_url, product_title, status,
         started_at, finished_at, error_message) in rows:
        listing_id = _resolve_or_create_orphan_listing(conn, product_url, store_name, product_title)
        # scraper_run_id must exist for the FK - if the parent run wasn't migrated
        # (e.g. its store no longer exists), skip this row too.
        run_row = conn.execute("SELECT id FROM scraper_runs WHERE id = ?", (run_id,)).fetchone()
        if not run_row:
            skipped += 1
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO listing_runs
                (id, scraper_run_id, store_listing_id, product_url, product_title,
                 status, started_at, finished_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (sku_run_id, run_id, listing_id, product_url, product_title,
             status, started_at, finished_at, error_message),
        )
        migrated += 1
    if skipped:
        print(f"Skipped {skipped} legacy sku_runs row(s) with no resolvable parent scraper_run.")
    return migrated, skipped


def _migrate_price_observations(conn: sqlite3.Connection) -> tuple[int, int]:
    if not _table_exists(conn, "prices"):
        return 0, 0

    rows = conn.execute(
        "SELECT execution_id, store_name, product_url, product_title, price_cash, "
        "price_installments, installment_count, currency, discount, is_available, "
        "parser_version, scraped_at FROM prices"
    ).fetchall()

    migrated = 0
    skipped = 0
    for (execution_id, store_name, product_url, product_title, price_cash,
         price_installments, installment_count, currency, discount, is_available,
         parser_version, scraped_at) in rows:
        listing_id = _resolve_or_create_orphan_listing(conn, product_url, store_name, product_title)
        if not listing_id:
            skipped += 1
            continue
        run_row = conn.execute(
            "SELECT id FROM scraper_runs WHERE id = ?", (execution_id,)
        ).fetchone()
        scraper_run_id = execution_id if run_row else None
        conn.execute(
            """
            INSERT OR IGNORE INTO price_observations
                (id, store_listing_id, scraper_run_id, price_cash, price_installments,
                 installment_count, currency, discount, is_available, parser_version, scraped_at)
            VALUES (lower(hex(randomblob(16))), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (listing_id, scraper_run_id, price_cash, price_installments, installment_count,
             currency, discount, is_available, parser_version, scraped_at),
        )
        migrated += 1
    if skipped:
        print(f"Skipped {skipped} legacy prices row(s) with no resolvable store_listings match.")
    return migrated, skipped


def _migrate_alert_rules(conn: sqlite3.Connection) -> tuple[int, int]:
    if not _table_exists(conn, "legacy_alert_rules"):
        return 0, 0

    rows = conn.execute(
        "SELECT rule_id, store_name, search_keyword, brand, model, threshold_type, "
        "threshold_value, is_active, created_at FROM legacy_alert_rules"
    ).fetchall()

    migrated = 0
    unmatched = 0
    for (rule_id, store_name, search_keyword, brand, model, threshold_type,
         threshold_value, is_active, created_at) in rows:
        store_id = None
        if store_name:
            store_row = conn.execute("SELECT id FROM stores WHERE slug = ?", (store_name,)).fetchone()
            store_id = store_row[0] if store_row else None

        gpu_model_id = None
        if brand and model:
            gm_row = conn.execute(
                """
                SELECT gm.id FROM gpu_models gm
                JOIN brands b ON b.id = gm.brand_id
                WHERE LOWER(b.name) = LOWER(?) AND LOWER(gm.model_name) = LOWER(?)
                """,
                (brand, model),
            ).fetchone()
            gpu_model_id = gm_row[0] if gm_row else None
            if gpu_model_id is None:
                unmatched += 1

        conn.execute(
            """
            INSERT OR IGNORE INTO alert_rules
                (id, store_id, gpu_model_id, search_keyword, threshold_type,
                 threshold_value, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (rule_id, store_id, gpu_model_id, search_keyword, threshold_type,
             threshold_value, is_active, created_at),
        )
        migrated += 1
    if unmatched:
        print(f"{unmatched} legacy alert_rules row(s) had a brand/model with no catalog match "
              f"(gpu_model_id left NULL - rule now matches any model).")
    return migrated, unmatched


def _migrate_alert_events(conn: sqlite3.Connection) -> tuple[int, int]:
    if not _table_exists(conn, "alert_history"):
        return 0, 0

    rows = conn.execute(
        "SELECT event_id, rule_id, product_url, price_cash, reason, triggered_at FROM alert_history"
    ).fetchall()

    migrated = 0
    skipped = 0
    for event_id, rule_id, product_url, price_cash, reason, triggered_at in rows:
        listing_row = conn.execute(
            "SELECT id FROM store_listings WHERE product_url = ?", (product_url,)
        ).fetchone()
        if not listing_row:
            skipped += 1
            continue
        obs_row = conn.execute(
            """
            SELECT id FROM price_observations
            WHERE store_listing_id = ? AND price_cash = ? AND scraped_at <= ?
            ORDER BY scraped_at DESC LIMIT 1
            """,
            (listing_row[0], price_cash, triggered_at),
        ).fetchone()
        if not obs_row:
            skipped += 1
            continue
        rule_row = conn.execute("SELECT id FROM alert_rules WHERE id = ?", (rule_id,)).fetchone()
        if not rule_row:
            skipped += 1
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO alert_events
                (id, alert_rule_id, price_observation_id, reason, triggered_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_id, rule_id, obs_row[0], reason, triggered_at),
        )
        migrated += 1
    if skipped:
        print(f"Skipped {skipped} legacy alert_history row(s) with no resolvable price_observations match "
              f"(acceptably lossy per the migration plan).")
    return migrated, skipped


def migrate_legacy_schema(db_path: str) -> None:
    if db_path == ":memory:" or not os.path.exists(db_path):
        print(f"{db_path!r} doesn't exist - nothing to migrate.")
        return

    backup_path = backup_database(db_path)
    if backup_path is None:
        print(f"WARNING: expected to back up {db_path} but backup_database() returned None.")
    else:
        print(f"Backed up {db_path} to {backup_path} before migrating.")

    conn = sqlite3.connect(db_path)
    try:
        if _already_migrated(conn):
            print("Database is already on the new schema (or has no legacy data) - nothing to do.")
            return

        conn.execute("BEGIN")
        _rename_reused_tables(conn)
    finally:
        conn.commit()
        conn.close()

    # initialize_schema uses aiosqlite on its own connection - run it after
    # committing/closing the rename transaction above so it sees the renamed
    # legacy tables and creates fresh scraper_runs/alert_rules/trigger_requests.
    asyncio.run(initialize_db_schema(db_path))

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")  # populate in dependency order manually, verify at the end
        conn.execute("BEGIN")

        _seed_stores(conn)
        _migrate_brands_chipsets_gpu_models(conn)
        listings_migrated, listings_skipped = _migrate_store_listings(conn)
        runs_migrated, runs_skipped = _migrate_scraper_runs(conn)
        listing_runs_migrated, listing_runs_skipped = _migrate_listing_runs(conn)
        prices_migrated, prices_skipped = _migrate_price_observations(conn)
        rules_migrated, rules_unmatched = _migrate_alert_rules(conn)
        events_migrated, events_skipped = _migrate_alert_events(conn)

        conn.commit()

        print("\nRunning PRAGMA foreign_key_check ...")
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            print(f"FOREIGN KEY VIOLATIONS FOUND ({len(fk_errors)}) - investigate before dropping legacy tables:")
            for err in fk_errors:
                print(f"  {err}")
        else:
            print("No foreign key violations found.")

        print("\n=== Migration summary ===")
        print(f"store_listings: {listings_migrated} migrated, {listings_skipped} skipped")
        print(f"scraper_runs:   {runs_migrated} migrated, {runs_skipped} skipped")
        print(f"listing_runs:   {listing_runs_migrated} migrated, {listing_runs_skipped} skipped")
        print(f"price_observations: {prices_migrated} migrated, {prices_skipped} skipped")
        print(f"alert_rules:    {rules_migrated} migrated, {rules_unmatched} with unmatched gpu_model")
        print(f"alert_events:   {events_migrated} migrated, {events_skipped} skipped (lossy by design)")

        print(
            "\nLegacy tables were left in place for manual verification. Once you're satisfied, "
            "drop them yourself:\n"
            "  DROP TABLE prices;\n"
            "  DROP TABLE target_urls;\n"
            "  DROP TABLE gpu_chipsets;\n"
            "  DROP TABLE sku_runs;\n"
            "  DROP TABLE alert_history;\n"
            "  DROP TABLE legacy_scraper_runs;\n"
            "  DROP TABLE legacy_alert_rules;\n"
            "  DROP TABLE legacy_trigger_requests;\n"
            "  DROP TABLE legacy_brands;\n"
            "  DROP TABLE legacy_gpu_models;\n"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else settings.db_path
    migrate_legacy_schema(target)
