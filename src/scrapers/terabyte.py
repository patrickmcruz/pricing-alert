import logging
import re
from decimal import Decimal
from typing import Any, List, Optional

from bs4 import BeautifulSoup
from pydantic import ValidationError

from src.core.base_scraper import BaseScraper, SelectorOutdatedException
from src.core.contract import PriceContract, ProductSKU

logger = logging.getLogger(__name__)


class TerabyteScraper(BaseScraper):
    """
    Scraper implementation for Terabyteshop.
    """

    def __init__(self):
        super().__init__(
            store_name="terabyte", base_url="https://www.terabyteshop.com.br"
        )

    def _clean_price(self, price_str: str) -> Decimal | None:
        """Helper to convert BRL price string to Decimal."""
        if not price_str:
            return None
        cleaned = re.sub(r"[R\$\s\.]", "", price_str)
        cleaned = cleaned.replace(",", ".")
        try:
            return Decimal(cleaned)
        except Exception:
            return None

    async def fetch(self, sku: ProductSKU, client: Any) -> str:
        raise NotImplementedError("Network fetch is not implemented yet.")

    def parse(self, document: str, sku: ProductSKU) -> Optional[PriceContract]:
        parser_version = "v1"
        selectors = self.load_selectors(parser_version)
        soup = BeautifulSoup(document, "lxml")

        title_elem = soup.select_one(selectors["title"])
        if not title_elem:
            raise SelectorOutdatedException(f"[{self.store_name}] Title selector '{selectors['title']}' failed.")
        title = title_elem.text.strip()

        price_cash_elem = soup.select_one(selectors["price_cash"])
        if not price_cash_elem:
            raise SelectorOutdatedException(f"[{self.store_name}] Cash price selector '{selectors['price_cash']}' failed.")
            
        price_cash_str = price_cash_elem.text.strip()
        price_cash = self._clean_price(price_cash_str)
        if price_cash is None or price_cash <= 0:
            return None

        price_inst_elem = soup.select_one(selectors["price_installments"])
        price_inst_str = price_inst_elem.text.strip() if price_inst_elem else ""
        price_installments = self._clean_price(price_inst_str)

        is_available = True
        if soup.find(string=re.compile(selectors["out_of_stock"], re.I)):
            is_available = False

        # Calculate discount if applicable
        discount = None
        if price_installments and price_installments > 0 and price_cash > 0:
            discount = price_installments - price_cash

        return PriceContract(
            store_name=self.store_name,
            search_keyword=sku.search_keyword,
            product_title=title,
            product_url=sku.product_url,
            price_cash=price_cash,
            price_installments=price_installments if price_installments and price_installments > 0 else None,
            currency="BRL",
            parser_version=f"{self.store_name}_{parser_version}",
            is_available=is_available,
            brand=sku.brand,
            model=sku.model,
            discount=discount
        )
