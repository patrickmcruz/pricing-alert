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
        raise NotImplementedError("Network fetch is not implemented yet.")

    def parse_search_grid(self, document: str, keyword: str) -> List[ProductSKU]:
        soup = BeautifulSoup(document, "lxml")
        skus = []
        cards = soup.find_all("div", class_="pbox")
        for card in cards:
            link_elem = card.find("a")
            if not link_elem or not link_elem.get("href"):
                continue
            url = str(link_elem.get("href"))
            
            title_elem = card.find(class_="prod-name")
            title = title_elem.text.strip() if title_elem else "Unknown"
            
            # Simple brand/model heuristic
            brand = None
            if "msi" in title.lower(): brand = "MSI"
            elif "gigabyte" in title.lower(): brand = "Gigabyte"
            elif "asus" in title.lower(): brand = "ASUS"
            
            model = None
            if "eagle" in title.lower(): model = "Eagle"
            elif "windforce" in title.lower(): model = "Windforce"
            
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
