import logging
from typing import List
import aiosqlite

from src.core.contract import PriceContract, ProductSKU
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
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS prices (
                        execution_id TEXT NOT NULL,
                        store_name TEXT NOT NULL,
                        search_keyword TEXT NOT NULL,
                        product_title TEXT NOT NULL,
                        product_url TEXT NOT NULL,
                        price_cash DECIMAL(10, 2) NOT NULL,
                        price_installments DECIMAL(10, 2),
                        installment_count INTEGER,
                        currency TEXT NOT NULL,
                        parser_version TEXT NOT NULL,
                        is_available BOOLEAN NOT NULL,
                        brand TEXT,
                        model TEXT,
                        discount DECIMAL(10, 2),
                        scraped_at TIMESTAMP NOT NULL
                    )
                """)
                
                # Safe migration: Add column if it doesn't exist
                try:
                    await db.execute("ALTER TABLE prices ADD COLUMN installment_count INTEGER")
                except aiosqlite.OperationalError:
                    pass # Column already exists
                
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS target_urls (
                        product_url TEXT PRIMARY KEY,
                        store_name TEXT NOT NULL,
                        search_keyword TEXT NOT NULL,
                        brand TEXT,
                        model TEXT,
                        product_title TEXT NOT NULL
                    )
                """)
                
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
                execution_id, store_name, search_keyword, product_title, product_url,
                brand, model, price_cash, price_installments, installment_count, discount, currency, parser_version,
                is_available, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        values = []
        for p in prices:
            values.append(
                (
                    str(p.execution_id),
                    p.store_name,
                    p.search_keyword,
                    p.product_title,
                    str(p.product_url),
                    p.brand,
                    p.model,
                    float(p.price_cash),
                    float(p.price_installments) if p.price_installments else None,
                    p.installment_count,
                    float(p.discount) if p.discount else None,
                    p.currency,
                    p.parser_version,
                    p.is_available,
                    p.scraped_at.isoformat(),
                )
            )

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executemany(query, values)
                await db.commit()
            logger.info("Successfully saved %d price records to SQLite.", len(prices))
        except Exception as e:
            logger.error("Failed to save price records to SQLite: %s", e)
            raise

    async def get_prices_by_keyword(self, keyword: str) -> List[PriceContract]:
        """
        Retrieves pricing history for a specific keyword, newest first.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM prices WHERE search_keyword = ? ORDER BY scraped_at DESC",
                (keyword,),
            )
            rows = await cursor.fetchall()

        return [
            PriceContract(
                execution_id=row["execution_id"],
                store_name=row["store_name"],
                search_keyword=row["search_keyword"],
                product_title=row["product_title"],
                product_url=row["product_url"],
                price_cash=row["price_cash"],
                price_installments=row["price_installments"],
                installment_count=row["installment_count"],
                currency=row["currency"],
                parser_version=row["parser_version"],
                is_available=bool(row["is_available"]),
                brand=row["brand"],
                model=row["model"],
                discount=row["discount"],
                scraped_at=row["scraped_at"],
            )
            for row in rows
        ]

    async def save_skus(self, skus: List[ProductSKU]) -> None:
        """
        Persists discovered SKUs to the database (upsert).
        """
        if not skus:
            return

        query = """
            INSERT OR REPLACE INTO target_urls (
                product_url, store_name, search_keyword, brand, model, product_title
            ) VALUES (?, ?, ?, ?, ?, ?)
        """

        values = [
            (
                str(sku.product_url),
                sku.store_name,
                sku.search_keyword,
                sku.brand,
                sku.model,
                sku.product_title,
            )
            for sku in skus
        ]

        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(query, values)
            await db.commit()
            logger.info("Saved %d SKUs to the database.", len(skus))

    async def get_target_skus(self, store_name: str) -> List[ProductSKU]:
        """
        Retrieves all SKUs to be scraped for a specific store.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT product_url, store_name, search_keyword, brand, model, product_title FROM target_urls WHERE store_name = ?", (store_name,)
            )
            rows = await cursor.fetchall()
            return [
                ProductSKU(
                    product_url=row[0], # type: ignore
                    store_name=row[1],
                    search_keyword=row[2],
                    brand=row[3],
                    model=row[4],
                    product_title=row[5]
                )
                for row in rows
            ]
