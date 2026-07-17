import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import asyncpg

from src.core.store import Store
from src.db.schema import connect
from src.repositories.store_repository import StoreRepository

logger = logging.getLogger(__name__)


async def get_or_create_store_id(
    db: asyncpg.Connection,
    slug: str,
    display_name: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    """
    Resolves a store slug to its id on an already-open connection, creating the
    store if it doesn't exist yet. Shared by every other Postgres repository
    that used to persist a free-text store_name directly (execution, trigger, price).
    """
    row = await db.fetchrow("SELECT id FROM stores WHERE slug = $1", slug)
    if row:
        return str(row["id"])
    store_id = str(uuid4())
    await db.execute(
        "INSERT INTO stores (id, slug, display_name, base_url, is_active, created_at) "
        "VALUES ($1, $2, $3, $4, true, $5)",
        store_id, slug, display_name or slug, base_url, datetime.now(timezone.utc),
    )
    return store_id


class PostgresStoreRepository(StoreRepository):
    """PostgreSQL implementation of StoreRepository, using the same database as prices."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    async def get_or_create_store(
        self, slug: str, display_name: Optional[str] = None, base_url: Optional[str] = None
    ) -> Store:
        async with connect(self.dsn) as db:
            store_id = await get_or_create_store_id(db, slug, display_name, base_url)
            row = await db.fetchrow("SELECT * FROM stores WHERE id = $1", store_id)
        return self._row_to_store(row)

    async def get_store_by_slug(self, slug: str) -> Optional[Store]:
        async with connect(self.dsn) as db:
            row = await db.fetchrow("SELECT * FROM stores WHERE slug = $1", slug)
        return self._row_to_store(row) if row else None

    async def list_stores(self) -> list[Store]:
        async with connect(self.dsn) as db:
            rows = await db.fetch("SELECT * FROM stores ORDER BY slug")
        return [self._row_to_store(row) for row in rows]

    @staticmethod
    def _row_to_store(row: asyncpg.Record) -> Store:
        return Store(
            id=str(row["id"]),
            slug=row["slug"],
            display_name=row["display_name"],
            base_url=row["base_url"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )
