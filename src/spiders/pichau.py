import logging
import urllib.parse
from typing import Any

from src.scrapers.pichau import extract_pichau_products
from src.spiders.base_spider import BaseSpider, DiscoveredSKU
from src.spiders.registry import register_spider

logger = logging.getLogger(__name__)


@register_spider("pichau")
class PichauSpider(BaseSpider):
    """
    Spider for Pichau (pichau.com.br).
    Navigates to Pichau's search page via Playwright and extracts embedded GraphQL products.
    Transport type: "browser".
    """

    def __init__(self):
        super().__init__(store_name="pichau", transport_type="browser")

    async def fetch_search_grid(self, search_keyword: str, category: str, client: Any) -> list[DiscoveredSKU]:
        """
        Navigates to Pichau search page using Playwright `client` and extracts embedded product JSON.
        """
        encoded_kw = urllib.parse.quote(search_keyword)
        search_url = f"https://www.pichau.com.br/search?q={encoded_kw}"

        discovered: list[DiscoveredSKU] = []
        try:
            await client.goto(search_url, wait_until="networkidle", timeout=30000)
            content = await client.content()

            products = extract_pichau_products(content)
            for prod in products:
                name = prod.get("name")
                url_key = prod.get("url_key")
                if not name or not url_key:
                    continue

                product_url = f"https://www.pichau.com.br/{url_key}"
                discovered.append(
                    DiscoveredSKU(
                        store_name=self.store_name,
                        search_keyword=search_keyword,
                        product_url=product_url,
                        product_title=name,
                        category=category,
                    )
                )
        except Exception as e:
            logger.error("[%s] Search grid fetch failed for keyword %r: %s", self.store_name, search_keyword, e)

        return discovered
