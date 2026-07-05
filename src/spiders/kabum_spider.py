import logging
from typing import Any, List

from bs4 import BeautifulSoup

from src.core.contract import ProductSKU
from src.spiders.base_spider import BaseSpider

logger = logging.getLogger(__name__)

class KabumSpider(BaseSpider):
    def __init__(self):
        super().__init__(store_name="kabum", base_url="https://www.kabum.com.br")

    async def fetch_search_page(self, keyword: str, client: Any) -> str:
        raise NotImplementedError("Network fetch is not implemented yet.")

    def parse_search_grid(self, document: str, keyword: str) -> List[ProductSKU]:
        soup = BeautifulSoup(document, "lxml")
        skus = []
        cards = soup.find_all("div", class_="productCard")
        for card in cards:
            link_elem = card.find("a", class_="productLink")
            if not link_elem or not link_elem.get("href"):
                continue
            url = str(link_elem.get("href"))
            
            title_elem = card.find(class_="nameCard")
            title = title_elem.text.strip() if title_elem else "Unknown"
            
            # Simple brand/model heuristic extraction from title
            brand = None
            if "msi" in title.lower(): brand = "MSI"
            elif "gigabyte" in title.lower(): brand = "Gigabyte"
            elif "asus" in title.lower(): brand = "ASUS"
            elif "galax" in title.lower(): brand = "GALAX"
            
            model = None
            if "ventus" in title.lower(): model = "Ventus"
            elif "gaming" in title.lower(): model = "Gaming"
            
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
