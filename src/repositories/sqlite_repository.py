import logging
from typing import List
import aiosqlite

from src.core.contract import PriceContract
from src.repositories.base_repository import PriceRepository

logger = logging.getLogger(__name__)


class SQLitePriceRepository(PriceRepository):
    """
    SQLite implementation of the PriceRepository using aiosqlite.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize_schema(self) -> None:
        """
        Creates the prices table if it does not exist.
        """
        query = """
        CREATE TABLE IF NOT EXISTS prices (
            execution_id TEXT NOT NULL,
            store_name TEXT NOT NULL,
            search_keyword TEXT NOT NULL,
            product_title TEXT NOT NULL,
            product_url TEXT NOT NULL,
            price_cash DECIMAL(10, 2) NOT NULL,
            price_installments DECIMAL(10, 2),
            currency TEXT DEFAULT 'BRL',
            is_available BOOLEAN NOT NULL,
            scraped_at TIMESTAMP NOT NULL
        )
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(query)
                # Create indexes for faster queries
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_search_keyword ON prices(search_keyword)"
                )
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_store_name ON prices(store_name)"
                )
                await db.commit()
            logger.info("SQLite schema initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize SQLite schema: %s", e)
            raise

    async def save_prices(self, prices: List[PriceContract]) -> None:
        """
        Persists a list of PriceContract objects to the SQLite database.
        """
        if not prices:
            return

        query = """
        INSERT INTO prices (
            execution_id,
            store_name,
            search_keyword,
            product_title,
            product_url,
            price_cash,
            price_installments,
            currency,
            is_available,
            scraped_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Convert Pydantic models to tuples for sqlite execution
        rows = [
            (
                str(p.execution_id),
                p.store_name,
                p.search_keyword,
                p.product_title,
                str(p.product_url),
                float(p.price_cash),
                (
                    float(p.price_installments)
                    if p.price_installments is not None
                    else None
                ),
                p.currency,
                p.is_available,
                p.scraped_at.isoformat(),
            )
            for p in prices
        ]

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executemany(query, rows)
                await db.commit()
            logger.info("Successfully saved %d price records to SQLite.", len(prices))
        except Exception as e:
            logger.error("Failed to save price records to SQLite: %s", e)
            raise

    async def get_prices_by_keyword(self, keyword: str) -> List[PriceContract]:
        """
        Retrieves pricing history for a specific keyword.
        """
        # NOTE: Deserialization mapping back to PriceContract logic goes here.
        # This will be fully implemented when the UI requires it.
        # For now, it returns an empty list to satisfy the abstract method signature.
        return []
