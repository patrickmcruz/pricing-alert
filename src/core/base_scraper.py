from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Optional
import logging

import os
import tomllib

from src.core.contract import PriceContract, ProductSKU
from src.core.utils import apply_jitter

logger = logging.getLogger(__name__)

class SelectorOutdatedException(Exception):
    """Raised when a scraper fails to find critical DOM elements using its current selectors."""
    pass


class BaseScraper(ABC):
    """
    Base abstraction for all scraper implementations.

    Concrete scrapers should implement only document retrieval
    and parsing logic.
    """

    #: Selects which ClientFactory PriceEngine injects into fetch() - "browser"
    #: (Playwright Page, default) for HTML scraping or "http" (httpx.AsyncClient)
    #: for scrapers hitting a JSON/REST API directly.
    transport_type: ClassVar[str] = "browser"

    def __init__(self, store_name: str, base_url: str):
        self.store_name = store_name
        self.base_url = base_url
        self.selectors_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "selectors", f"{store_name}.toml"
        )
        
    def load_selectors(self, version: str) -> dict[str, str]:
        """Loads CSS selectors from the store's TOML config."""
        if not os.path.exists(self.selectors_path):
            raise FileNotFoundError(f"Selector config not found: {self.selectors_path}")
            
        with open(self.selectors_path, "rb") as f:
            data = tomllib.load(f)
            
        if version not in data:
            raise ValueError(f"Version '{version}' not found in {self.store_name}.toml")
            
        return data[version]

    @abstractmethod
    async def fetch(
        self,
        sku: ProductSKU,
        client: Any,
    ) -> str:
        """
        Performs only network I/O.

        Returns the raw document retrieved from the store.
        """

    @abstractmethod
    def parse(
        self,
        document: str,
        sku: ProductSKU,
    ) -> Optional[PriceContract]:
        """
        Parses the retrieved document and returns validated
        PriceContract objects.

        This method must be deterministic and independently
        unit-testable using static fixtures.
        """

    async def execute(
        self,
        sku: ProductSKU,
        client: Any,
    ) -> Optional[PriceContract]:
        """
        Executes the complete scraping pipeline.
        """

        await apply_jitter()

        logger.info(
            "Starting scraper '%s' for sku '%s'",
            self.store_name,
            sku.product_url,
        )

        document = await self.fetch(sku, client)

        if not document:
            return None

        return self.parse(document, sku)
