import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings
from src.db.schema import connect


async def main() -> None:
    async with connect(settings.db_dsn) as db:
        rows = await db.fetch("SELECT COUNT(*) AS c FROM price_observations")
        print("price_observations=", rows[0]["c"])
        rows2 = await db.fetch(
            "SELECT l.product_url, cp.price_cash, cp.is_available "
            "FROM price_observations cp "
            "JOIN listings l ON l.id = cp.listing_id "
            "WHERE l.product_url LIKE 'https://www.pichau.com.br/%' "
            "ORDER BY cp.scraped_at DESC LIMIT 5"
        )
        for row in rows2:
            print(row["product_url"], row["price_cash"], row["is_available"])


if __name__ == "__main__":
    asyncio.run(main())
