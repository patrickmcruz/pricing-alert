import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import aiosqlite

from src.core.contract import LegacyTargetUrlRow, PriceContract, ProductSKU
from src.db.schema import connect
from src.repositories.base_repository import PriceRepository
from src.repositories.sqlite_store_repository import get_or_create_store_id

logger = logging.getLogger(__name__)


class SQLitePriceRepository(PriceRepository):
    """
    SQLite implementation of the PriceRepository using aiosqlite.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def save_prices(
        self, prices: List[PriceContract], scraper_run_id: Optional[UUID] = None
    ) -> List[str]:
        """
        Persists a list of PriceContract objects to the SQLite database.
        Returns the generated price_observations.id values, in the same order
        as the input list.
        """
        if not prices:
            return []

        observation_ids: List[str] = []
        try:
            async with connect(self.db_path) as db:
                for p in prices:
                    cursor = await db.execute(
                        "SELECT id FROM store_listings WHERE product_url = ?",
                        (str(p.product_url),),
                    )
                    row = await cursor.fetchone()
                    if not row:
                        raise ValueError(
                            f"No store_listings row found for product_url {p.product_url!r} - "
                            "cannot save a price for an untracked listing."
                        )
                    store_listing_id = row[0]
                    observation_id = str(uuid4())
                    observation_ids.append(observation_id)
                    await db.execute(
                        """
                        INSERT INTO price_observations (
                            id, store_listing_id, scraper_run_id, price_cash, price_installments,
                            installment_count, currency, discount, is_available, parser_version,
                            scraped_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            observation_id,
                            store_listing_id,
                            str(scraper_run_id) if scraper_run_id else None,
                            float(p.price_cash),
                            float(p.price_installments) if p.price_installments else None,
                            p.installment_count,
                            p.currency,
                            float(p.discount) if p.discount else None,
                            p.is_available,
                            p.parser_version,
                            p.scraped_at.isoformat(),
                        ),
                    )
                await db.commit()
            logger.info("Successfully saved %d price records to SQLite.", len(prices))
            return observation_ids
        except Exception as e:
            logger.error("Failed to save price records to SQLite: %s", e)
            raise

    async def get_prices_by_keyword(self, keyword: str) -> List[PriceContract]:
        """
        Retrieves pricing history for a specific keyword, newest first.
        """
        async with connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT po.id AS observation_id, s.slug AS store_name, sl.search_keyword,
                       sl.product_title, sl.product_url, po.price_cash, po.price_installments,
                       po.installment_count, po.currency, po.parser_version, po.is_available,
                       b.name AS brand, gm.model_name AS model, po.discount, po.scraped_at,
                       sl.gpu_model_id
                FROM price_observations po
                JOIN store_listings sl ON sl.id = po.store_listing_id
                JOIN stores s ON s.id = sl.store_id
                JOIN gpu_models gm ON gm.id = sl.gpu_model_id
                JOIN brands b ON b.id = gm.brand_id
                WHERE sl.search_keyword = ?
                ORDER BY po.scraped_at DESC
                """,
                (keyword,),
            )
            rows = await cursor.fetchall()

        return [
            PriceContract(
                execution_id=row["observation_id"],
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
        Persists discovered SKUs to the database (upsert by product_url).
        Uses an ON CONFLICT upsert rather than INSERT OR REPLACE, since the
        latter would delete-then-reinsert the row under a new id, which fails
        under FK enforcement once any price_observations/listing_runs
        reference the existing row.
        """
        if not skus:
            return

        now = datetime.now(timezone.utc).isoformat()

        async with connect(self.db_path) as db:
            for sku in skus:
                store_id = await get_or_create_store_id(db, sku.store_name)
                listing_id = str(uuid4())
                await db.execute(
                    """
                    INSERT INTO store_listings (
                        id, store_id, gpu_model_id, product_url, product_title,
                        search_keyword, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(product_url) DO UPDATE SET
                        store_id = excluded.store_id,
                        gpu_model_id = excluded.gpu_model_id,
                        product_title = excluded.product_title,
                        search_keyword = excluded.search_keyword,
                        is_active = 1,
                        updated_at = excluded.updated_at
                    """,
                    (
                        listing_id,
                        store_id,
                        sku.gpu_model_id,
                        str(sku.product_url),
                        sku.product_title,
                        sku.search_keyword,
                        now,
                        now,
                    ),
                )
            await db.commit()
            logger.info("Saved %d SKUs to the database.", len(skus))

    _TARGET_SKU_JOIN_SELECT = """
        SELECT sl.product_url, s.slug, sl.search_keyword, sl.gpu_model_id, sl.product_title,
               b.name, gm.model_name
        FROM store_listings sl
        JOIN stores s ON s.id = sl.store_id
        JOIN gpu_models gm ON gm.id = sl.gpu_model_id
        JOIN brands b ON b.id = gm.brand_id
        WHERE sl.is_active = 1
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
        Retrieves all active SKUs to be scraped for a specific store. Rows
        whose gpu_model_id hasn't been resolved yet (see DiscoveryEngine's
        backfill pass) are excluded by the JOIN rather than raising.
        """
        async with connect(self.db_path) as db:
            cursor = await db.execute(
                self._TARGET_SKU_JOIN_SELECT + " AND s.slug = ?", (store_name,)
            )
            rows = await cursor.fetchall()
            return [self._row_to_sku(row) for row in rows]

    async def list_all_skus(self) -> List[ProductSKU]:
        """
        Retrieves all active tracked SKUs across every store. Rows whose
        gpu_model_id hasn't been resolved yet are excluded by the JOIN rather
        than raising.
        """
        async with connect(self.db_path) as db:
            cursor = await db.execute(self._TARGET_SKU_JOIN_SELECT)
            rows = await cursor.fetchall()
            return [self._row_to_sku(row) for row in rows]

    async def delete_sku(self, product_url: str) -> None:
        """
        Soft-deletes a tracked SKU by its product URL (is_active = 0), so its
        price_observations/listing_runs history isn't orphaned by FK
        enforcement. No-op if it doesn't exist.
        """
        async with connect(self.db_path) as db:
            await db.execute(
                "UPDATE store_listings SET is_active = 0, updated_at = ? WHERE product_url = ?",
                (datetime.now(timezone.utc).isoformat(), product_url),
            )
            await db.commit()
            logger.info("Soft-deleted SKU %s from the database.", product_url)

    async def list_target_urls_missing_gpu_model(self) -> List[LegacyTargetUrlRow]:
        """
        Returns store_listings rows whose gpu_model_id hasn't been resolved
        yet. In practice this is unlikely with the new NOT NULL gpu_model_id
        column, but kept for backward compatibility with DiscoveryEngine's
        one-time backfill against rows written before the catalog existed.
        """
        async with connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT sl.product_url, s.slug AS store_name, sl.search_keyword, sl.product_title
                FROM store_listings sl
                JOIN stores s ON s.id = sl.store_id
                WHERE sl.gpu_model_id IS NULL
                """
            )
            rows = await cursor.fetchall()
            return [
                LegacyTargetUrlRow(
                    product_url=row["product_url"],
                    store_name=row["store_name"],
                    search_keyword=row["search_keyword"],
                    brand=None,
                    model=None,
                    product_title=row["product_title"],
                )
                for row in rows
            ]

    async def set_sku_gpu_model_id(self, product_url: str, gpu_model_id: str) -> None:
        """Backfills gpu_model_id for a single store_listings row, by product_url."""
        async with connect(self.db_path) as db:
            await db.execute(
                "UPDATE store_listings SET gpu_model_id = ? WHERE product_url = ?",
                (gpu_model_id, product_url),
            )
            await db.commit()
