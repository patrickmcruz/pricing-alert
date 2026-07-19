from abc import ABC, abstractmethod
from typing import List

from src.core.contract import TargetUrlEntry


class TargetUrlRepository(ABC):
    """
    Abstract interface for the `target_urls` table - the raw manifest of
    record DiscoveryEngine resolves into the product catalog. See
    specs/target-urls-table/spec.md.
    """

    @abstractmethod
    async def list_all(self) -> List[TargetUrlEntry]:
        """Every row currently in the manifest, across every store."""

    @abstractmethod
    async def upsert_many(self, entries: List[TargetUrlEntry]) -> int:
        """
        Inserts new rows; an entry whose product_url already exists is left
        untouched (same idempotency contract the old JSON-based discovery
        scripts maintained by hand). Returns how many rows were actually new.
        """
