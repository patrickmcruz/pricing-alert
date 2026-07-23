import logging
import re
import urllib.parse
from typing import Any

from src.spiders.base_spider import BaseSpider, DiscoveredSKU
from src.spiders.registry import register_spider

logger = logging.getLogger(__name__)


@register_spider("mercado-livre")
class MercadoLivreSpider(BaseSpider):
    """
    Spider for Mercado Livre (mercado-livre).
    Queries the official Mercado Libre REST Search API (/sites/MLB/search).
    Transport type: "http" (pure REST client, no browser/Playwright needed).
    """

    def __init__(self):
        super().__init__(store_name="mercado-livre", transport_type="http")

    async def fetch_search_grid(self, search_keyword: str, category: str, client: Any) -> list[DiscoveredSKU]:
        """
        Executes a REST query against Mercado Libre's search API.
        `client` is expected to be an httpx.AsyncClient instance.
        """
        encoded_query = urllib.parse.quote(search_keyword)
        api_url = f"https://api.mercadolibre.com/sites/MLB/search?q={encoded_query}&limit=20"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        discovered: list[DiscoveredSKU] = []

        # 1. Try REST API search
        try:
            response = await client.get(api_url, headers=headers, timeout=15.0)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                for item in results:
                    permalink = item.get("permalink")
                    title = item.get("title")
                    if permalink and title:
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
                    return discovered
        except Exception:
            pass

        # 2. Fallback to HTML search page
        html_url = f"https://lista.mercadolivre.com.br/{urllib.parse.quote(search_keyword)}"
        try:
            from bs4 import BeautifulSoup
            res = await client.get(html_url, headers=headers, follow_redirects=True, timeout=15.0)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "lxml")
                for a_tag in soup.find_all("a", href=re.compile(r"MLB-\d+|/p/MLB")):
                    href = a_tag.get("href", "")
                    title = a_tag.get_text(" ", strip=True) or a_tag.get("title", "")
                    if href and title and len(title) > 10 and href.startswith("http"):
                        discovered.append(
                            DiscoveredSKU(
                                store_name=self.store_name,
                                search_keyword=search_keyword,
                                product_url=href,
                                product_title=title,
                                category=category,
                            )
                        )
        except Exception as e:
            logger.error("[%s] Search grid fallback failed for keyword %r: %s", self.store_name, search_keyword, e)

        return discovered
