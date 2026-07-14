import logging
from typing import List
import aiosqlite

from src.core.contract import LegacyTargetUrlRow, PriceContract, ProductSKU
from src.repositories.base_repository import PriceRepository
from src.repositories.sqlite_catalog_repository import ensure_catalog_tables

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

                # Safe migration: FK into the catalog's gpu_models table (see
                # src/repositories/sqlite_catalog_repository.py). Nullable - historical
                # rows scraped before the catalog existed won't have one.
                try:
                    await db.execute("ALTER TABLE prices ADD COLUMN gpu_model_id TEXT")
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

                # Safe migration: brand/model above are no longer written to (they're
                # superseded by gpu_model_id, resolved via a JOIN on read - see
                # get_target_skus/list_all_skus below) and are kept only so existing
                # rows aren't destructively rewritten. New/updated rows carry a real
                # FK into gpu_models instead of free text.
                try:
                    await db.execute("ALTER TABLE target_urls ADD COLUMN gpu_model_id TEXT")
                except aiosqlite.OperationalError:
                    pass # Column already exists

                # get_target_skus/list_all_skus JOIN against these - see ensure_catalog_tables
                # for why initializing the price schema alone must create them too.
                await ensure_catalog_tables(db)

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
                is_available, scraped_at, gpu_model_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    p.gpu_model_id,
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
                gpu_model_id=row["gpu_model_id"],
            )
            for row in rows
        ]

    async def save_skus(self, skus: List[ProductSKU]) -> None:
        """
        Persists discovered SKUs to the database (upsert). brand/model are not
        written - target_urls stores gpu_model_id (a FK into the catalog) instead;
        see get_target_skus/list_all_skus for how they're resolved back on read.
        """
        if not skus:
            return

        query = """
            INSERT OR REPLACE INTO target_urls (
                product_url, store_name, search_keyword, gpu_model_id, product_title
            ) VALUES (?, ?, ?, ?, ?)
        """

        values = [
            (
                str(sku.product_url),
                sku.store_name,
                sku.search_keyword,
                sku.gpu_model_id,
                sku.product_title,
            )
            for sku in skus
        ]

        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(query, values)
            await db.commit()
            logger.info("Saved %d SKUs to the database.", len(skus))

    _TARGET_SKU_JOIN_SELECT = """
        SELECT t.product_url, t.store_name, t.search_keyword, t.gpu_model_id, t.product_title,
               b.name, gm.variant_name
        FROM target_urls t
        JOIN gpu_models gm ON gm.id = t.gpu_model_id
        JOIN brands b ON b.id = gm.brand_id
    """

    @staticmethod
    def _row_to_sku(row) -> ProductSKU:
        return ProductSKU(
            product_url=row[0],  # type: ignore
            store_name=row[1],
            search_keyword=row[2],
            gpu_model_id=row[3],
            product_title=row[4],
            brand=row[5],
            model=row[6],
        )

    async def get_target_skus(self, store_name: str) -> List[ProductSKU]:
        """
        Retrieves all SKUs to be scraped for a specific store. Rows whose
        gpu_model_id hasn't been resolved yet (see DiscoveryEngine's backfill
        pass) are excluded by the JOIN rather than raising.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                self._TARGET_SKU_JOIN_SELECT + " WHERE t.store_name = ?", (store_name,)
            )
            rows = await cursor.fetchall()
            return [self._row_to_sku(row) for row in rows]

    async def list_all_skus(self) -> List[ProductSKU]:
        """
        Retrieves all tracked SKUs across every store. Rows whose gpu_model_id
        hasn't been resolved yet are excluded by the JOIN rather than raising.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(self._TARGET_SKU_JOIN_SELECT)
            rows = await cursor.fetchall()
            return [self._row_to_sku(row) for row in rows]

    async def delete_sku(self, product_url: str) -> None:
        """
        Removes a tracked SKU by its product URL. No-op if it doesn't exist.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM target_urls WHERE product_url = ?", (product_url,))
            await db.commit()
            logger.info("Deleted SKU %s from the database.", product_url)

    async def list_target_urls_missing_gpu_model(self) -> List[LegacyTargetUrlRow]:
        """
        Returns target_urls rows whose gpu_model_id hasn't been resolved yet.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT product_url, store_name, search_keyword, brand, model, product_title "
                "FROM target_urls WHERE gpu_model_id IS NULL"
            )
            rows = await cursor.fetchall()
            return [
                LegacyTargetUrlRow(
                    product_url=row["product_url"],
                    store_name=row["store_name"],
                    search_keyword=row["search_keyword"],
                    brand=row["brand"],
                    model=row["model"],
                    product_title=row["product_title"],
                )
                for row in rows
            ]

    async def set_sku_gpu_model_id(self, product_url: str, gpu_model_id: str) -> None:
        """Backfills gpu_model_id for a single target_urls row, by product_url."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE target_urls SET gpu_model_id = ? WHERE product_url = ?",
                (gpu_model_id, product_url),
            )
            await db.commit()
