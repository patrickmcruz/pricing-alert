"""Caps anuncio to a small number of models per (loja, chipset) pair,
so a full scrape in development only hits a handful of URLs per store instead
of dozens - fast iteration when testing scrapers/engine/alerts locally.

Soft-deletes the rest (is_active = false), same as PostgresPriceRepository.delete_sku,
so existing coleta_preco/listing_runs history for the trimmed listings
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

import psycopg

from src.core.config import settings


def trim_dev_listings(dsn: str, keep: int = 2) -> None:
    if settings.env == "production":
        raise SystemExit(
            "Refusing to trim anuncio in the production environment - "
            "production is meant to keep every GPU listing it has ever discovered."
        )

    conn = psycopg.connect(dsn)
    try:
        with conn.cursor() as cur:
            # One row per (store, chipset) - the granularity we cap - not per
            # product, so multiple models sharing a chipset (e.g. Terabyte's
            # 39 different RTX 5070 listings) actually get collapsed down to
            # `keep` instead of being a no-op (each product already has only
            # one active listing per store, so capping per-product never had
            # anything to trim).
            cur.execute(
                """
                SELECT a.store_id, l.slug, p.specs->>'chipset'
                FROM listings a
                JOIN stores l ON l.id = a.store_id
                JOIN products p ON p.id = a.product_id
                WHERE a.is_active = true
                GROUP BY a.store_id, l.slug, p.specs->>'chipset'
                """
            )
            groups = cur.fetchall()

            total_deactivated = 0
            for store_id, store_slug, chipset_name in groups:
                cur.execute(
                    """
                    SELECT a.id FROM listings a
                    JOIN products p ON p.id = a.product_id
                    WHERE a.store_id = %s AND a.is_active = true AND p.specs->>'chipset' = %s
                    ORDER BY a.created_at
                    """,
                    (store_id, chipset_name),
                )
                listing_ids = [row[0] for row in cur.fetchall()]
                to_deactivate = listing_ids[keep:]
                if not to_deactivate:
                    continue
                cur.executemany(
                    "UPDATE listings SET is_active = false, updated_at = now() WHERE id = %s",
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
    trim_dev_listings(settings.db_dsn, keep=keep_arg)
