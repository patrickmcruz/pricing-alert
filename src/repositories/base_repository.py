from abc import ABC, abstractmethod
from typing import List

from src.core.contract import PriceContract


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
