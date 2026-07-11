import logging
import re
from decimal import Decimal
from typing import Any, Optional

from bs4 import BeautifulSoup

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
        """
        Retrieves the raw HTML document from the store.
        """
        from src.core.utils import simulate_human_interaction
        try:
            await client.goto(str(sku.product_url), wait_until="domcontentloaded", timeout=45000)
            await simulate_human_interaction(client)
            return await client.content()
        except Exception as e:
            logger.error("[%s] Network fetch failed for '%s': %s", self.store_name, sku.product_url, e)
            return ""

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
        
        is_available = True
        if soup.find(string=re.compile(selectors["out_of_stock"], re.I)):
            is_available = False
            
        if (price_cash is None or price_cash <= 0) and is_available:
            return None
            
        if not is_available and price_cash is None:
            price_cash = Decimal('0.00')

        price_inst_elem = soup.select_one(selectors["price_installments"])
        price_inst_str = price_inst_elem.text.strip() if price_inst_elem else ""
        price_installments = self._clean_price(price_inst_str)

        installment_count = None
        if "installment_count" in selectors:
            count_elem = soup.select_one(selectors["installment_count"])
            if count_elem:
                count_str = re.sub(r"\D", "", count_elem.text)
                if count_str:
                    installment_count = int(count_str)

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
            installment_count=installment_count,
            currency="BRL",
            parser_version=f"{self.store_name}_{parser_version}",
            is_available=is_available,
            brand=sku.brand,
            model=sku.model,
            discount=discount
        )
