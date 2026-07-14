"""Caps store_listings to a small number of models per (store, chipset) pair,
so a full scrape in development only hits a handful of URLs per store instead
of dozens - fast iteration when testing scrapers/engine/alerts locally.

Soft-deletes the rest (is_active = 0), same as SQLitePriceRepository.delete_sku,
so existing price_observations/listing_runs history for the trimmed listings
isn't orphaned - they just stop being scraped.

Refuses to run against the production environment: production is meant to keep
every GPU listing it has ever discovered, never trimmed.

Run manually: `APP_ENV=develop python scripts/trim_dev_listings.py [keep]`
(keep defaults to 2).
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import sqlite3

from src.core.config import settings


def trim_dev_listings(db_path: str, keep: int = 2) -> None:
    if settings.env == "production":
        raise SystemExit(
            "Refusing to trim store_listings in the production environment - "
            "production is meant to keep every GPU listing it has ever discovered."
        )

    conn = sqlite3.connect(db_path)
    try:
        groups = conn.execute(
            """
            SELECT sl.store_id, s.slug, gm.chipset_id, c.name
            FROM store_listings sl
            JOIN stores s ON s.id = sl.store_id
            JOIN gpu_models gm ON gm.id = sl.gpu_model_id
            JOIN chipsets c ON c.id = gm.chipset_id
            WHERE sl.is_active = 1
            GROUP BY sl.store_id, gm.chipset_id
            """
        ).fetchall()

        total_deactivated = 0
        for store_id, store_slug, chipset_id, chipset_name in groups:
            listing_ids = [
                row[0]
                for row in conn.execute(
                    """
                    SELECT sl.id FROM store_listings sl
                    JOIN gpu_models gm ON gm.id = sl.gpu_model_id
                    WHERE sl.store_id = ? AND gm.chipset_id = ? AND sl.is_active = 1
                    ORDER BY sl.created_at
                    """,
                    (store_id, chipset_id),
                ).fetchall()
            ]
            to_deactivate = listing_ids[keep:]
            if not to_deactivate:
                continue
            conn.executemany(
                "UPDATE store_listings SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
                [(lid,) for lid in to_deactivate],
            )
            total_deactivated += len(to_deactivate)
            print(
                f"{store_slug} / {chipset_name}: kept {min(len(listing_ids), keep)}, "
                f"deactivated {len(to_deactivate)}"
            )

        conn.commit()
        print(f"\nDone. Deactivated {total_deactivated} listing(s) total.")
    finally:
        conn.close()


if __name__ == "__main__":
    keep_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    trim_dev_listings(settings.db_path, keep=keep_arg)
