from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List
import asyncio
import logging
import random

from src.core.contract import PriceContract

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Base abstraction for all scraper implementations.

    Concrete scrapers should implement only document retrieval
    and parsing logic.
    """

    def __init__(
        self,
        store_name: str,
        base_url: str,
    ):
        self.store_name = store_name
        self.base_url = base_url

    async def apply_jitter(
        self,
        min_seconds: float = 3.0,
        max_seconds: float = 8.0,
    ) -> None:
        """
        Applies a randomized asynchronous delay to reduce
        deterministic request patterns.
        """
        await asyncio.sleep(random.uniform(min_seconds, max_seconds))

    @abstractmethod
    async def fetch(
        self,
        keyword: str,
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
        keyword: str,
    ) -> List[PriceContract]:
        """
        Parses the retrieved document and returns validated
        PriceContract objects.

        This method must be deterministic and independently
        unit-testable using static fixtures.
        """

    async def execute(
        self,
        keyword: str,
        client: Any,
    ) -> List[PriceContract]:
        """
        Executes the complete scraping pipeline.
        """

        await self.apply_jitter()

        logger.info(
            "Starting scraper '%s' for keyword '%s'",
            self.store_name,
            keyword,
        )

        document = await self.fetch(keyword, client)

        if not document:
            return []

        return self.parse(document, keyword)
