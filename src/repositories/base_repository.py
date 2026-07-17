from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.core.contract import LegacyTargetUrlRow, PriceContract, ProductSKU


class PriceRepository(ABC):
    """
    Abstract interface for persisting scraped pricing data.
    """

    @abstractmethod
    async def save_prices(
        self, prices: List[PriceContract], scraper_run_id: Optional[UUID] = None
    ) -> List[str]:
        """
        Persists a list of PriceContract objects to the underlying database.
        Returns the generated coleta_preco.id values, in the same order
        as the input list.
        """
        pass

    @abstractmethod
    async def get_prices_by_keyword(self, keyword: str) -> List[PriceContract]:
        """
        Retrieves pricing history for a specific keyword.
        """
        pass

    @abstractmethod
    async def save_skus(self, skus: List[ProductSKU]) -> None:
        """
        Persists discovered SKUs to the database.
        """
        pass

    @abstractmethod
    async def get_target_skus(self, store_name: str) -> List[ProductSKU]:
        """
        Retrieves all SKUs to be scraped for a specific store.
        """
        pass

    @abstractmethod
    async def list_all_skus(self) -> List[ProductSKU]:
        """
        Retrieves all tracked SKUs across every store.
        """
        pass

    @abstractmethod
    async def delete_sku(self, product_url: str) -> None:
        """
        Soft-deletes a tracked SKU by its product URL (is_active = false), so its
        coleta_preco/listing_runs history isn't orphaned. No-op if it
        doesn't exist.
        """
        pass

    @abstractmethod
    async def list_target_urls_missing_produto(self) -> List[LegacyTargetUrlRow]:
        """
        Returns anuncio rows whose produto_id hasn't been resolved yet
        (written before the catalog existed). Used only by
        DiscoveryEngine's one-time backfill.
        """
        pass

    @abstractmethod
    async def set_sku_produto_id(self, product_url: str, produto_id: str) -> None:
        """Backfills produto_id for a single anuncio row, by product_url."""
        pass
