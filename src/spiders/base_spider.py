from abc import ABC, abstractmethod
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DiscoveredSKU(BaseModel):
    """
    Pydantic v2 model representing a product SKU discovered by a store spider
    from a search grid or search API.
    """
    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)

    store_name: str
    search_keyword: str
    product_url: str
    product_title: str
    brand: Optional[str] = None
    model: Optional[str] = None
    category: str = Field(default="gpu")


class BaseSpider(ABC):
    """
    Abstract Base Class for Store Spiders responsible for dynamic catalog discovery.
    """

    def __init__(self, store_name: str, transport_type: str = "http"):
        self.store_name = store_name
        self.transport_type = transport_type

    @abstractmethod
    async def fetch_search_grid(self, search_keyword: str, category: str, client: Any) -> list[DiscoveredSKU]:
        """
        Performs network I/O to fetch and parse the search grid / search API for the given keyword.
        Returns a list of DiscoveredSKU objects.
        """
        pass

    async def execute(self, search_keyword: str, category: str, client: Any) -> list[DiscoveredSKU]:
        """
        Orchestrates spider execution.
        """
        return await self.fetch_search_grid(search_keyword, category, client)
