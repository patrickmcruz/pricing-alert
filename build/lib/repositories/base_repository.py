from abc import ABC, abstractmethod
from typing import List

from src.core.contract import PriceContract, ProductSKU


class PriceRepository(ABC):
    """
    Abstract interface for persisting scraped pricing data.
    """

    @abstractmethod
    async def save_prices(self, prices: List[PriceContract]) -> None:
        """
        Persists a list of PriceContract objects to the underlying database.
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
