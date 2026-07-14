from __future__ import annotations

from typing import Any, Protocol


class ClientFactory(Protocol):
    """
    Contract shared by BrowserFactory and HTTPClientFactory, so PriceEngine can
    pick the right transport per-scraper via BaseScraper.transport_type.
    """

    async def create(self, scraper: Any) -> Any: ...

    async def close(self, client: Any) -> None: ...
