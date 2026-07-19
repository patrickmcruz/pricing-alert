from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from src.core.contract import TargetUrlEntry
from src.db.schema import affected_rows, connect
from src.repositories.target_url_repository import TargetUrlRepository


class PostgresTargetUrlRepository(TargetUrlRepository):
    """PostgreSQL implementation of TargetUrlRepository, using the same database as everything else."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    async def list_all(self) -> List[TargetUrlEntry]:
        async with connect(self.dsn) as db:
            rows = await db.fetch(
                "SELECT store_name, search_keyword, product_url, brand, model, product_title "
                "FROM target_urls ORDER BY store_name, product_url"
            )
            return [
                TargetUrlEntry(
                    store_name=row["store_name"],
                    search_keyword=row["search_keyword"],
                    product_url=row["product_url"],
                    brand=row["brand"],
                    model=row["model"],
                    product_title=row["product_title"],
                )
                for row in rows
            ]

    async def upsert_many(self, entries: List[TargetUrlEntry]) -> int:
        if not entries:
            return 0

        inserted = 0
        async with connect(self.dsn) as db:
            for entry in entries:
                status = await db.execute(
                    """
                    INSERT INTO target_urls
                        (id, store_name, search_keyword, product_url, brand, model, product_title, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (product_url) DO NOTHING
                    """,
                    str(uuid4()), entry.store_name, entry.search_keyword, entry.product_url,
                    entry.brand, entry.model, entry.product_title, datetime.now(timezone.utc),
                )
                inserted += affected_rows(status)
        return inserted
