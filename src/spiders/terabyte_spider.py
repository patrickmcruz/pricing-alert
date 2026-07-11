import logging
from typing import Any, List

from bs4 import BeautifulSoup

from src.core.contract import ProductSKU
from src.spiders.base_spider import BaseSpider

logger = logging.getLogger(__name__)

class TerabyteSpider(BaseSpider):
    def __init__(self):
        super().__init__(store_name="terabyte", base_url="https://www.terabyteshop.com.br")

    async def fetch_search_page(self, keyword: str, client: Any) -> str:
        from urllib.parse import quote_plus
        search_url = f"{self.base_url}/busca?str={quote_plus(keyword)}"
        try:
            await client.goto(search_url, wait_until="networkidle", timeout=30000)
            return await client.content()
        except Exception as e:
            logger.error("[%s] Network fetch failed for search keyword '%s': %s", self.store_name, keyword, e)
            return ""

    def parse_search_grid(self, document: str, keyword: str) -> List[ProductSKU]:
        soup = BeautifulSoup(document, "lxml")
        skus = []
        cards = soup.find_all("a", class_="tss-result-card")
        for card in cards:
            if not card or not card.get("href"):
                continue
            
            raw_url = str(card.get("href"))
            if raw_url.startswith("/"):
                url = f"{self.base_url}{raw_url}"
            else:
                url = raw_url
            
            title_elem = card.find(class_="tss-result-title") or card.find(class_="prod-name")
            title = title_elem.text.strip() if title_elem else "Unknown"
            
            # Simple brand/model heuristic
            brand = None
            if "msi" in title.lower():
                brand = "MSI"
            elif "gigabyte" in title.lower():
                brand = "Gigabyte"
            elif "asus" in title.lower():
                brand = "ASUS"
            elif "colorful" in title.lower():
                brand = "Colorful"
            
            model = None
            if "eagle" in title.lower():
                model = "Eagle"
            elif "windforce" in title.lower():
                model = "Windforce"
            elif "battle ax" in title.lower() or "battle-ax" in title.lower():
                model = "Battle AX"
            
            sku = ProductSKU(
                store_name=self.store_name,
                search_keyword=keyword,
                product_url=url,  # type: ignore
                brand=brand,
                model=model,
                product_title=title
            )
            skus.append(sku)
        return skus
