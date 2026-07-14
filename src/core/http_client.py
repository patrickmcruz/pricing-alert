import httpx
from typing import Any

from src.core.config import settings

class HTTPClientFactory:
    """Factory for managing httpx async clients."""

    async def create(self, scraper: Any) -> httpx.AsyncClient:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        client = httpx.AsyncClient(
            http2=True, headers=headers, follow_redirects=True, timeout=settings.http_timeout_seconds
        )
        return client

    async def close(self, client: httpx.AsyncClient) -> None:
        await client.aclose()
