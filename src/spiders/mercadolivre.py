import logging
import re
import urllib.parse
from typing import Any

from src.core.config import settings
from src.spiders.base_spider import BaseSpider, DiscoveredSKU
from src.spiders.registry import register_spider

logger = logging.getLogger(__name__)

# Non-GPU accessory / prebuilt computer keywords to ignore during discovery
_EXCLUDED_TITLE_WORDS = [
    "cabo", "suporte", "riser", "waterblock", "bloco",
    "backplate", "adesivo", "notebook", "laptop", "extensor",
    "pc ", "pc gamer", "pc elite", "computador", "xtreme pc", "workstation"
]


@register_spider("mercado-livre")
class MercadoLivreSpider(BaseSpider):
    """
    Spider for Mercado Livre (mercado-livre).
    Queries the official Mercado Libre REST Search API (/products/search & /sites/MLB/search).
    Transport type: "http" (pure REST client, no browser/Playwright needed).
    """

    def __init__(self):
        super().__init__(store_name="mercado-livre", transport_type="http")
        self._access_token: str | None = None

    async def _ensure_authenticated(self, client: Any) -> None:
        """Obtains an OAuth access token if credentials are provided."""
        if self._access_token:
            return

        if settings.ml_app_id and settings.ml_secret_key:
            try:
                auth_url = "https://api.mercadolibre.com/oauth/token"
                payload = {
                    "grant_type": "client_credentials",
                    "client_id": settings.ml_app_id,
                    "client_secret": settings.ml_secret_key,
                }
                res = await client.post(auth_url, data=payload, timeout=10.0)
                if res.status_code == 200:
                    self._access_token = res.json().get("access_token")
                    logger.info("[%s] Spider authenticated via OAuth client_credentials.", self.store_name)
            except Exception as e:
                logger.warning("[%s] OAuth authentication failed: %s", self.store_name, e)

    async def fetch_search_grid(self, search_keyword: str, category: str, client: Any) -> list[DiscoveredSKU]:
        """
        Executes REST queries against Mercado Libre's product search API.
        `client` is expected to be an httpx.AsyncClient instance.
        """
        await self._ensure_authenticated(client)

        encoded_query = urllib.parse.quote(search_keyword)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        discovered: list[DiscoveredSKU] = []

        # 1. Query Catalog Products API (/products/search)
        api_url = f"https://api.mercadolibre.com/products/search?status=active&site_id=MLB&q={encoded_query}&limit=30"
        try:
            response = await client.get(api_url, headers=headers, timeout=15.0)
            if response.status_code == 200:
                results = response.json().get("results", [])
                for item in results:
                    title = item.get("name") or item.get("title")
                    pid = item.get("id")
                    permalink = item.get("permalink") or f"https://www.mercadolivre.com.br/p/{pid}"

                    if not title or not permalink:
                        continue

                    lower_title = title.lower()
                    if any(word in lower_title for word in _EXCLUDED_TITLE_WORDS):
                        continue

                    discovered.append(
                        DiscoveredSKU(
                            store_name=self.store_name,
                            search_keyword=search_keyword,
                            product_url=permalink,
                            product_title=title,
                            category=category,
                        )
                    )

                if discovered:
                    logger.info("[%s] Discovered %d catalog SKUs for keyword %r", self.store_name, len(discovered), search_keyword)
                    return discovered
        except Exception as e:
            logger.warning("[%s] Catalog products search failed for keyword %r: %s", self.store_name, search_keyword, e)

        # 2. Fallback to /sites/MLB/search API
        site_search_url = f"https://api.mercadolibre.com/sites/MLB/search?q={encoded_query}&limit=30"
        try:
            response = await client.get(site_search_url, headers=headers, timeout=15.0)
            if response.status_code == 200:
                results = response.json().get("results", [])
                for item in results:
                    permalink = item.get("permalink")
                    title = item.get("title")

                    if not title or not permalink:
                        continue

                    lower_title = title.lower()
                    if any(word in lower_title for word in _EXCLUDED_TITLE_WORDS):
                        continue

                    discovered.append(
                        DiscoveredSKU(
                            store_name=self.store_name,
                            search_keyword=search_keyword,
                            product_url=permalink,
                            product_title=title,
                            category=category,
                        )
                    )

                if discovered:
                    logger.info("[%s] Discovered %d site SKUs for keyword %r", self.store_name, len(discovered), search_keyword)
        except Exception as e:
            logger.error("[%s] Site search failed for keyword %r: %s", self.store_name, search_keyword, e)

        return discovered
