from abc import ABC, abstractmethod
from typing import Any, List
import logging
import random
import asyncio

from src.core.contract import ProductSKU

logger = logging.getLogger(__name__)

class BaseSpider(ABC):
    """
    Base abstraction for Discovery Spiders.
    Responsible for navigating search pages and discovering product SKUs.
    """
    
    def __init__(self, store_name: str, base_url: str):
        self.store_name = store_name
        self.base_url = base_url

    async def apply_jitter(self, min_seconds: float = 3.0, max_seconds: float = 8.0) -> None:
        await asyncio.sleep(random.uniform(min_seconds, max_seconds))

    @abstractmethod
    async def fetch_search_page(self, keyword: str, client: Any) -> str:
        """Fetches the search results page."""

    @abstractmethod
    def parse_search_grid(self, document: str, keyword: str) -> List[ProductSKU]:
        """Parses the search grid to extract SKU metadata and URLs."""

    async def discover(self, keyword: str, client: Any) -> List[ProductSKU]:
        await self.apply_jitter()
        logger.info("Starting Discovery Spider '%s' for keyword '%s'", self.store_name, keyword)
        document = await self.fetch_search_page(keyword, client)
        if not document:
            return []
        return self.parse_search_grid(document, keyword)
