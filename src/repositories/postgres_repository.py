import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from src.core.contract import LegacyTargetUrlRow, PriceContract, ProductSKU
from src.db.schema import connect
from src.repositories.base_repository import PriceRepository
from src.repositories.postgres_store_repository import get_or_create_store_id

logger = logging.getLogger(__name__)


class PostgresPriceRepository(PriceRepository):
    """PostgreSQL implementation of PriceRepository using asyncpg."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    async def save_prices(
        self, prices: List[PriceContract], scraper_run_id: Optional[UUID] = None
    ) -> List[str]:
        """
        Persists a list of PriceContract objects to Postgres, all within a
        single transaction. Returns the generated coleta_preco.id values, in
        the same order as the input list.
        """
        if not prices:
            return []

        observation_ids: List[str] = []
        try:
            async with connect(self.dsn) as db:
                async with db.transaction():
                    for p in prices:
                        row = await db.fetchrow(
                            "SELECT id FROM anuncio WHERE product_url = $1", str(p.product_url)
                        )
                        if not row:
                            raise ValueError(
                                f"No anuncio row found for product_url {p.product_url!r} - "
                                "cannot save a price for an untracked listing."
                            )
                        anuncio_id = row["id"]
                        observation_id = str(uuid4())
                        observation_ids.append(observation_id)
                        await db.execute(
                            """
                            INSERT INTO coleta_preco (
                                id, anuncio_id, scraper_run_id, price_cash, price_installments,
                                installment_count, currency, discount, is_available, parser_version,
                                scraped_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            """,
                            observation_id,
                            anuncio_id,
                            str(scraper_run_id) if scraper_run_id else None,
                            p.price_cash,
                            p.price_installments,
                            p.installment_count,
                            p.currency,
                            p.discount,
                            p.is_available,
                            p.parser_version,
                            p.scraped_at,
                        )
            logger.info("Successfully saved %d price records to PostgreSQL.", len(prices))
            return observation_ids
        except Exception as e:
            logger.error("Failed to save price records to PostgreSQL: %s", e)
            raise

    async def get_prices_by_keyword(self, keyword: str) -> List[PriceContract]:
        """
        Retrieves pricing history for a specific keyword, newest first.
        """
        async with connect(self.dsn) as db:
            rows = await db.fetch(
                """
                SELECT cp.id AS observation_id, l.slug AS store_name, a.search_keyword,
                       a.product_title, a.product_url, cp.price_cash, cp.price_installments,
                       cp.installment_count, cp.currency, cp.parser_version, cp.is_available,
                       ma.nome AS brand, p.nome AS model, cp.discount, cp.scraped_at,
                       a.produto_id
                FROM coleta_preco cp
                JOIN anuncio a ON a.id = cp.anuncio_id
                JOIN loja l ON l.id = a.loja_id
                JOIN produto p ON p.id = a.produto_id
                JOIN marca ma ON ma.id = p.marca_id
                WHERE a.search_keyword = $1
                ORDER BY cp.scraped_at DESC
                """,
                keyword,
            )

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
                is_available=row["is_available"],
                brand=row["brand"],
                model=row["model"],
                discount=row["discount"],
                scraped_at=row["scraped_at"],
                produto_id=str(row["produto_id"]),
            )
            for row in rows
        ]

    async def save_skus(self, skus: List[ProductSKU]) -> None:
        """
        Persists discovered SKUs to the database (upsert by product_url).
        Uses an ON CONFLICT upsert rather than delete-then-reinsert, since the
        latter would create the row under a new id, which fails under FK
        enforcement once any coleta_preco/listing_runs reference it.
        """
        if not skus:
            return

        now = datetime.now(timezone.utc)

        async with connect(self.dsn) as db:
            async with db.transaction():
                for sku in skus:
                    store_id = await get_or_create_store_id(db, sku.store_name)
                    listing_id = str(uuid4())
                    await db.execute(
                        """
                        INSERT INTO anuncio (
                            id, loja_id, produto_id, product_url, product_title,
                            search_keyword, is_active, created_at, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, true, $7, $8)
                        ON CONFLICT (product_url) DO UPDATE SET
                            loja_id = EXCLUDED.loja_id,
                            produto_id = EXCLUDED.produto_id,
                            product_title = EXCLUDED.product_title,
                            search_keyword = EXCLUDED.search_keyword,
                            is_active = true,
                            updated_at = EXCLUDED.updated_at
                        """,
                        listing_id,
                        store_id,
                        sku.produto_id,
                        str(sku.product_url),
                        sku.product_title,
                        sku.search_keyword,
                        now,
                        now,
                    )
            logger.info("Saved %d SKUs to the database.", len(skus))

    _TARGET_SKU_JOIN_SELECT = """
        SELECT a.product_url, l.slug, a.search_keyword, a.produto_id, a.product_title,
               ma.nome, p.nome
        FROM anuncio a
        JOIN loja l ON l.id = a.loja_id
        JOIN produto p ON p.id = a.produto_id
        JOIN marca ma ON ma.id = p.marca_id
        WHERE a.is_active = true
    """

    @staticmethod
    def _row_to_sku(row) -> ProductSKU:
        return ProductSKU(
            product_url=row[0],
            store_name=row[1],
            search_keyword=row[2],
            produto_id=str(row[3]),
            product_title=row[4],
            brand=row[5],
            model=row[6],
        )

    async def get_target_skus(self, store_name: str) -> List[ProductSKU]:
        """
        Retrieves all active SKUs to be scraped for a specific store. Rows
        whose produto_id hasn't been resolved yet (see DiscoveryEngine's
        backfill pass) are excluded by the JOIN rather than raising.
        """
        async with connect(self.dsn) as db:
            rows = await db.fetch(self._TARGET_SKU_JOIN_SELECT + " AND l.slug = $1", store_name)
            return [self._row_to_sku(row) for row in rows]

    async def list_all_skus(self) -> List[ProductSKU]:
        """
        Retrieves all active tracked SKUs across every store. Rows whose
        produto_id hasn't been resolved yet are excluded by the JOIN rather
        than raising.
        """
        async with connect(self.dsn) as db:
            rows = await db.fetch(self._TARGET_SKU_JOIN_SELECT)
            return [self._row_to_sku(row) for row in rows]

    async def delete_sku(self, product_url: str) -> None:
        """
        Soft-deletes a tracked SKU by its product URL (is_active = false), so
        its coleta_preco/listing_runs history isn't orphaned by FK
        enforcement. No-op if it doesn't exist.
        """
        async with connect(self.dsn) as db:
            await db.execute(
                "UPDATE anuncio SET is_active = false, updated_at = $1 WHERE product_url = $2",
                datetime.now(timezone.utc), product_url,
            )
            logger.info("Soft-deleted SKU %s from the database.", product_url)

    async def list_target_urls_missing_produto(self) -> List[LegacyTargetUrlRow]:
        """
        Returns anuncio rows whose produto_id hasn't been resolved yet. In
        practice this is unlikely with the NOT NULL produto_id column, but
        kept for backward compatibility with DiscoveryEngine's one-time
        backfill against rows written before the catalog existed.
        """
        async with connect(self.dsn) as db:
            rows = await db.fetch(
                """
                SELECT a.product_url, l.slug AS store_name, a.search_keyword, a.product_title
                FROM anuncio a
                JOIN loja l ON l.id = a.loja_id
                WHERE a.produto_id IS NULL
                """
            )
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

    async def set_sku_produto_id(self, product_url: str, produto_id: str) -> None:
        """Backfills produto_id for a single anuncio row, by product_url."""
        async with connect(self.dsn) as db:
            await db.execute(
                "UPDATE anuncio SET produto_id = $1 WHERE product_url = $2",
                produto_id, product_url,
            )
