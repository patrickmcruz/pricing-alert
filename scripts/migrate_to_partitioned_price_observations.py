import asyncio
import os
import sys
import logging

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings
from src.db.schema import connect, ensure_monthly_partitions

logger = logging.getLogger(__name__)


async def migrate_partitioning():
    print(f"Connecting to database: {settings.db_dsn}")
    async with connect(settings.db_dsn) as db:
        # Check if price_observations is partitioned
        row = await db.fetchrow("""
            SELECT relkind FROM pg_class WHERE relname = 'price_observations'
        """)
        if not row:
            print("price_observations table does not exist. Nothing to migrate.")
            return

        relkind = row["relkind"]
        if relkind == 'p':
            print("price_observations is ALREADY a partitioned table. Migration not needed.")
            return

        print("Converting unpartitioned price_observations to partitioned table...")
        
        # 1. Rename old table
        await db.execute("ALTER TABLE price_observations RENAME TO price_observations_old;")

        # 2. Create partitioned master table
        await db.execute("""
            CREATE TABLE price_observations (
                id                     UUID NOT NULL,
                listing_id             UUID NOT NULL REFERENCES listings(id),
                scraper_run_id         UUID REFERENCES scraper_runs(id),
                price_cash             NUMERIC(12,2) NOT NULL,
                price_installments     NUMERIC(12,2),
                installment_count      INTEGER,
                currency               TEXT NOT NULL,
                discount                NUMERIC(12,2),
                is_available           BOOLEAN NOT NULL,
                parser_version         TEXT NOT NULL,
                scraped_at             TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (id, scraped_at)
            ) PARTITION BY RANGE (scraped_at);
        """)

        # 3. Create default partition & monthly partitions
        await db.execute("CREATE TABLE price_observations_default PARTITION OF price_observations DEFAULT;")
        await ensure_monthly_partitions(db)

        # 4. Migrate existing data
        print("Migrating historical observations to partitioned table...")
        await db.execute("""
            INSERT INTO price_observations (
                id, listing_id, scraper_run_id, price_cash, price_installments,
                installment_count, currency, discount, is_available, parser_version, scraped_at
            )
            SELECT id, listing_id, scraper_run_id, price_cash, price_installments,
                   installment_count, currency, discount, is_available, parser_version, scraped_at
            FROM price_observations_old;
        """)

        # 5. Drop old table
        await db.execute("DROP TABLE price_observations_old CASCADE;")
        print("Successfully migrated price_observations to partitioned table!")


if __name__ == "__main__":
    asyncio.run(migrate_partitioning())
