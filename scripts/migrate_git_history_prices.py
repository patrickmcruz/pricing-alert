"""One-shot migration: recovers price history from every historical revision
of data/prices.db and data/prices_dev.db across git history (main branch) and
imports it into the CURRENT database (whatever settings.db_dsn/APP_ENV
resolves to).

Why this is needed: those .db files were full SQLite snapshots committed at
various points before the project moved to Postgres (see git log -- data/
prices.db). Each commit's snapshot is cumulative, so the same price
observation appears in many commits - naive re-import would duplicate rows
many times over. This script:

  1. Walks git history for every commit that touched either file, and
     extracts each *unique* blob (by content hash) via `git cat-file`, so an
     unchanged file across consecutive commits is only read once.
  2. Reads every row of each blob's old ad-hoc `prices` table (schema varied
     slightly across the project's early history - some snapshots lack
     parser_version/brand/model/installment_count; this tolerates all three
     shapes seen in git log).
  3. Deduplicates by `execution_id` (a stable UUID minted once per price
     observation in the old schema - never mutated between snapshots),
     preferring whichever copy of a row has the most complete columns.
  4. For each deduplicated row, resolves the target anuncio (listing) by
     product_url in the current DB and inserts a coleta_preco row, reusing
     the original execution_id as the new row's id so the insert is
     idempotent (ON CONFLICT DO NOTHING) - safe to re-run.

Rows whose product_url has no matching anuncio in the current DB (dummy seed
URLs from early dev, or listings later removed from tracking) are skipped and
counted, not fabricated - same "acceptably lossy" stance as
scripts/migrate_legacy_schema.py.

Run manually: `python scripts/migrate_git_history_prices.py [--apply]`
Without --apply it only reports what WOULD be migrated (dry run).
"""
import argparse
import asyncio
import os
import subprocess
import sqlite3
import sys
import tempfile
from datetime import datetime
from typing import Optional
from uuid import UUID

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings
from src.db.schema import connect, initialize_schema as initialize_db_schema
from scripts.backup_db import backup_database

HISTORICAL_PATHS = ["data/prices.db", "data/prices_dev.db"]
GIT_REF = "main"


def _is_valid_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _unique_blobs(repo_root: str) -> list[str]:
    """Returns every unique blob SHA ever committed to HISTORICAL_PATHS on GIT_REF."""
    blobs: set[str] = set()
    for path in HISTORICAL_PATHS:
        out = subprocess.run(
            ["git", "log", GIT_REF, "--format=%H", "--", path],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.split()
        for commit in out:
            ls = subprocess.run(
                ["git", "ls-tree", commit, "--", path],
                cwd=repo_root, capture_output=True, text=True, check=True,
            ).stdout.strip()
            if not ls:
                continue
            blob_sha = ls.split()[2]
            blobs.add(blob_sha)
    return sorted(blobs)


def _extract_blob(repo_root: str, blob_sha: str, dest_dir: str) -> str:
    dest = os.path.join(dest_dir, f"{blob_sha}.db")
    with open(dest, "wb") as f:
        subprocess.run(["git", "cat-file", "-p", blob_sha], cwd=repo_root, stdout=f, check=True)
    return dest


def _read_prices(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "prices" not in tables:
            return []
        cols = [r[1] for r in conn.execute("PRAGMA table_info(prices)").fetchall()]
        rows = conn.execute(f"SELECT {', '.join(cols)} FROM prices").fetchall()
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def _collect_and_dedupe(repo_root: str) -> list[dict]:
    blobs = _unique_blobs(repo_root)
    print(f"Found {len(blobs)} unique historical blob(s) across {HISTORICAL_PATHS}.")

    by_id: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for blob_sha in blobs:
            db_path = _extract_blob(repo_root, blob_sha, tmp)
            for row in _read_prices(db_path):
                eid = row.get("execution_id")
                if not eid or not _is_valid_uuid(eid):
                    continue
                existing = by_id.get(eid)
                if existing is None:
                    by_id[eid] = row
                else:
                    # Prefer whichever copy has more non-null columns (schema
                    # gained parser_version/brand/model/installment_count
                    # partway through history; the rows themselves never
                    # diverge in value once both have a given column).
                    if sum(v is not None for v in row.values()) > sum(v is not None for v in existing.values()):
                        by_id[eid] = row

    print(f"Deduplicated to {len(by_id)} distinct price observation(s) "
          f"across {len(set(r['product_url'] for r in by_id.values()))} product URL(s).")
    return list(by_id.values())


async def _migrate(rows: list[dict], apply: bool, dsn: str) -> None:
    await initialize_db_schema(dsn)

    migrated = 0
    skipped_no_listing = 0
    already_present = 0

    async with connect(dsn) as db:
        for row in rows:
            listing = await db.fetchrow(
                "SELECT id FROM anuncio WHERE product_url = $1", row["product_url"]
            )
            if not listing:
                skipped_no_listing += 1
                continue

            exists = await db.fetchval(
                "SELECT 1 FROM coleta_preco WHERE id = $1", row["execution_id"]
            )
            if exists:
                already_present += 1
                continue

            migrated += 1
            if not apply:
                continue

            await db.execute(
                """
                INSERT INTO coleta_preco (
                    id, anuncio_id, scraper_run_id, price_cash, price_installments,
                    installment_count, currency, discount, is_available, parser_version,
                    scraped_at
                ) VALUES ($1, $2, NULL, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (id) DO NOTHING
                """,
                row["execution_id"],
                listing["id"],
                row["price_cash"],
                row.get("price_installments"),
                row.get("installment_count"),
                row.get("currency") or "BRL",
                row.get("discount"),
                bool(row["is_available"]),
                row.get("parser_version") or "legacy_git_history",
                datetime.fromisoformat(row["scraped_at"]),
            )

    print("\n=== Migration summary ===")
    print(f"{'Migrated' if apply else 'Would migrate'}: {migrated}")
    print(f"Already present (idempotent re-run): {already_present}")
    print(f"Skipped (no matching anuncio.product_url in current DB): {skipped_no_listing}")
    if not apply:
        print("\nDry run only - re-run with --apply to write these rows.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually write rows (default: dry run).")
    parser.add_argument(
        "--dsn", default=None,
        help="Override settings.db_dsn - needed to reach [production]'s db_host=\"db\" "
             "(docker-internal only) from the host, e.g. "
             "postgresql://pricing:pricing@localhost:5432/pricing",
    )
    args = parser.parse_args()
    dsn = args.dsn or settings.db_dsn
    print(f"Target database: {dsn}\n")

    if args.apply:
        backup_path = backup_database(dsn, keep=settings.backup_retention_count)
        if backup_path:
            print(f"Backed up current DB to {backup_path} before migrating.\n")
        else:
            print("WARNING: could not create a backup (pg_dump not found?) - proceeding anyway.\n")

    rows = _collect_and_dedupe(PROJECT_ROOT)
    asyncio.run(_migrate(rows, apply=args.apply, dsn=dsn))


if __name__ == "__main__":
    main()
