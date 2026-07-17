import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings
from src.db.schema import connect


async def main():
    async with connect(settings.db_dsn) as db:
        print("Prices for Mercado Livre:")
        rows = await db.fetch(
            """
            SELECT cp.* FROM price_observations cp
            JOIN listings a ON a.id = cp.listing_id
            JOIN stores l ON l.id = a.store_id
            WHERE l.slug = 'mercado-livre'
            """
        )
        print(rows)

        print("\nTarget URLs for Mercado Livre:")
        rows = await db.fetch(
            """
            SELECT a.* FROM listings a
            JOIN stores l ON l.id = a.store_id
            WHERE l.slug = 'mercado-livre'
            """
        )
        print(rows)


if __name__ == "__main__":
    asyncio.run(main())
