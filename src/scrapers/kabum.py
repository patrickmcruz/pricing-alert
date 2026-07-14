import logging
import re
from typing import Any, Optional

from bs4 import BeautifulSoup

from src.core.base_scraper import BaseScraper, SelectorOutdatedException
from src.core.config import settings
from src.core.contract import PriceContract, ProductSKU
from src.core.contract_factory import build_price_contract
from src.core.parsing_utils import clean_brl_price, compute_discount, has_out_of_stock_marker
from src.core.registry import register_scraper

logger = logging.getLogger(__name__)


@register_scraper
class KabumScraper(BaseScraper):
    """
    Scraper implementation for Kabum.
    """

    def __init__(self):
        super().__init__(store_name="kabum", base_url="https://www.kabum.com.br")

    async def fetch(self, sku: ProductSKU, client: Any) -> str:
        """
        Retrieves the raw HTML document from the store using Playwright.
        """
        try:
            # client is a Playwright Page object here
            await client.goto(
                str(sku.product_url), wait_until="networkidle", timeout=settings.navigation_timeout_ms
            )
            return await client.content()
        except Exception as e:
            logger.error("[%s] Network fetch failed for %s: %s", self.store_name, sku.product_url, e)
            return ""

    def parse(self, document: str, sku: ProductSKU) -> Optional[PriceContract]:
        """
        Parses the Kabum product page.
        """
        parser_version = "v2"
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
        if price_cash is None or price_cash <= 0:
            return None

        price_inst_elem = soup.select_one(selectors["price_installments"])
        price_inst_str = price_inst_elem.text.strip() if price_inst_elem else ""
        price_installments = clean_brl_price(price_inst_str)

        is_available = not has_out_of_stock_marker(soup, selectors["out_of_stock"])

        # Extract installment count if selector is present
        installment_count = None
        if "installment_count" in selectors:
            try:
                # The provided CSS selector contains escaped colons and brackets. BeautifulSoup handles this better with CSS Selectors,
                # but long selectors can fail in BS4. We use it and fallback gracefully.
                inst_elem = soup.select_one(selectors["installment_count"])
                if inst_elem:
                    text = inst_elem.text.strip()
                    # e.g., "10x" -> 10
                    match = re.search(r'(\d+)x', text, re.IGNORECASE)
                    if match:
                        installment_count = int(match.group(1))
            except Exception as e:
                logger.warning("[%s] Failed to extract installment_count: %s", self.store_name, e)

        # Fix installment total if only installment value was extracted
        if price_installments and price_cash and installment_count:
            if price_installments < price_cash:
                price_installments = price_installments * installment_count

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
