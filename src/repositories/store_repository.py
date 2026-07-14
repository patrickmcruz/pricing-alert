from abc import ABC, abstractmethod
from typing import List, Optional

from src.core.store import Store


class StoreRepository(ABC):
    """
    Abstract interface for the normalized stores table - every other table
    that used to carry a free-text store_name now references stores.id instead.
    """

    @abstractmethod
    async def get_or_create_store(
        self, slug: str, display_name: Optional[str] = None, base_url: Optional[str] = None
    ) -> Store:
        """Case-sensitive get-or-create by slug."""

    @abstractmethod
    async def get_store_by_slug(self, slug: str) -> Optional[Store]:
        """Returns a Store by slug, or None if it doesn't exist."""

    @abstractmethod
    async def list_stores(self) -> List[Store]:
        """Returns every registered store."""
