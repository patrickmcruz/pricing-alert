import asyncio
import os
import sys
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.config import settings
from src.core.title_parser import TitleParserRegistry
from src.db.schema import connect


async def backfill():
    print(f"Connecting to database: {settings.db_dsn}")
    async with connect(settings.db_dsn) as db:
        rows = await db.fetch("""
            SELECT p.id, p.name, p.specs, l.product_title, l.search_keyword
            FROM products p
            LEFT JOIN listings l ON l.product_id = p.id
        """)
        print(f"Found {len(rows)} product record(s) to process.")

        updated_count = 0
        for row in rows:
            prod_id = str(row["id"])
            title = row["product_title"] or row["name"] or ""
            keyword = row["search_keyword"] or ""

            parsed = TitleParserRegistry.parse_gpu(title, search_keyword=keyword)
            specs = row["specs"] if isinstance(row["specs"], dict) else json.loads(row["specs"] or "{}")
            
            existing_chipset = specs.get("chipset")
            parsed_dict = parsed.to_dict()
            if existing_chipset:
                parsed_dict["chipset"] = existing_chipset

            # Merge parsed attributes into specs
            specs.update(parsed_dict)

            await db.execute("""
                UPDATE products
                SET mpn = $1,
                    product_line = $2,
                    is_oc = $3,
                    specs = $4
                WHERE id = $5
            """, parsed.mpn, parsed.product_line, parsed.is_oc, specs, prod_id)
            updated_count += 1

        print(f"Successfully backfilled structured attributes for {updated_count} product(s).")


if __name__ == "__main__":
    asyncio.run(backfill())
