import logging
import re
import urllib.parse
from typing import Any, List
from bs4 import BeautifulSoup

from src.spiders.base_spider import BaseSpider, DiscoveredSKU
from src.spiders.registry import register_spider

logger = logging.getLogger(__name__)


@register_spider("kabum")
class KabumSpider(BaseSpider):
    """
    Spider for KaBuM! (kabum.com.br).
    Navigates to KaBuM search page via Playwright and extracts product links.
    Transport type: "browser".
    """

    def __init__(self):
        super().__init__(store_name="kabum", transport_type="browser")

    async def fetch_search_grid(self, search_keyword: str, category: str, client: Any) -> list[DiscoveredSKU]:
        """
        Navigates to KaBuM search page using Playwright `client` and parses product cards.
        """
        encoded_kw = urllib.parse.quote(search_keyword)
        search_url = f"https://www.kabum.com.br/busca/{encoded_kw}"

        discovered: list[DiscoveredSKU] = []
        try:
            await client.goto(search_url, wait_until="networkidle", timeout=30000)
            content = await client.content()
            soup = BeautifulSoup(content, "lxml")

            for a_tag in soup.find_all("a", href=re.compile(r"/produto/\d+/")):
                href = a_tag.get("href", "")
                title = a_tag.get_text(" ", strip=True) or a_tag.get("title", "")
                if not href or not title or len(title) < 5:
                    continue

                full_url = href if href.startswith("http") else f"https://www.kabum.com.br{href}"
                discovered.append(
                    DiscoveredSKU(
                        store_name=self.store_name,
                        search_keyword=search_keyword,
                        product_url=full_url,
                        product_title=title,
                        category=category,
                    )
                )
        except Exception as e:
            logger.error("[%s] Search grid fetch failed for keyword %r: %s", self.store_name, search_keyword, e)

        return discovered
