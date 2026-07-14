import logging
import re
from decimal import Decimal
from typing import Any, Optional

from bs4 import BeautifulSoup

from src.core.base_scraper import BaseScraper, SelectorOutdatedException
from src.core.contract import PriceContract, ProductSKU
from src.core.contract_factory import build_price_contract
from src.core.parsing_utils import clean_brl_price, compute_discount, has_out_of_stock_marker
from src.core.registry import register_scraper

logger = logging.getLogger(__name__)


@register_scraper
class TerabyteScraper(BaseScraper):
    """
    Scraper implementation for Terabyteshop.
    """

    def __init__(self):
        super().__init__(
            store_name="terabyte", base_url="https://www.terabyteshop.com.br"
        )

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
        price_cash = clean_brl_price(price_cash_str)

        is_available = not has_out_of_stock_marker(soup, selectors["out_of_stock"])

        if (price_cash is None or price_cash <= 0) and is_available:
            return None

        if not is_available and price_cash is None:
            price_cash = Decimal('0.00')
        assert price_cash is not None

        price_inst_elem = soup.select_one(selectors["price_installments"])
        price_inst_str = price_inst_elem.text.strip() if price_inst_elem else ""
        price_installments = clean_brl_price(price_inst_str)

        installment_count = None
        if "installment_count" in selectors:
            count_elem = soup.select_one(selectors["installment_count"])
            if count_elem:
                count_str = re.sub(r"\D", "", count_elem.text)
                if count_str:
                    installment_count = int(count_str)

        return build_price_contract(
            self,
            sku,
            price_cash=price_cash,
            price_installments=price_installments,
            installment_count=installment_count,
            product_title=title,
            parser_version=f"{self.store_name}_{parser_version}",
            is_available=is_available,
            discount=compute_discount(price_cash, price_installments),
        )
