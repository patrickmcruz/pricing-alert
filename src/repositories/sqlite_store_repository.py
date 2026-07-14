import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

import aiosqlite

from src.core.store import Store
from src.db.schema import connect
from src.repositories.store_repository import StoreRepository

logger = logging.getLogger(__name__)


async def get_or_create_store_id(
    db: aiosqlite.Connection,
    slug: str,
    display_name: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    """
    Resolves a store slug to its id on an already-open connection, creating the
    store if it doesn't exist yet. Shared by every other SQLite repository that
    used to persist a free-text store_name directly (execution, trigger, price).
    """
    cursor = await db.execute("SELECT id FROM stores WHERE slug = ?", (slug,))
    row = await cursor.fetchone()
    if row:
        return row[0]
    store_id = str(uuid4())
    await db.execute(
        "INSERT INTO stores (id, slug, display_name, base_url, is_active, created_at) "
        "VALUES (?, ?, ?, ?, 1, ?)",
        (store_id, slug, display_name or slug, base_url, datetime.now(timezone.utc).isoformat()),
    )
    return store_id


class SQLiteStoreRepository(StoreRepository):
    """SQLite implementation of StoreRepository, using the same db file as prices."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def get_or_create_store(
        self, slug: str, display_name: Optional[str] = None, base_url: Optional[str] = None
    ) -> Store:
        async with connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            store_id = await get_or_create_store_id(db, slug, display_name, base_url)
            await db.commit()
            cursor = await db.execute("SELECT * FROM stores WHERE id = ?", (store_id,))
            row = await cursor.fetchone()
        return self._row_to_store(row)

    async def get_store_by_slug(self, slug: str) -> Optional[Store]:
        async with connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM stores WHERE slug = ?", (slug,))
            row = await cursor.fetchone()
        return self._row_to_store(row) if row else None

    async def list_stores(self) -> List[Store]:
        async with connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM stores ORDER BY slug")
            rows = await cursor.fetchall()
        return [self._row_to_store(row) for row in rows]

    @staticmethod
    def _row_to_store(row: aiosqlite.Row) -> Store:
        return Store(
            id=row["id"],
            slug=row["slug"],
            display_name=row["display_name"],
            base_url=row["base_url"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )
