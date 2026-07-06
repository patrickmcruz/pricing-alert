import logging
import re
from decimal import Decimal
from typing import Any, List, Optional

from bs4 import BeautifulSoup
from pydantic import ValidationError

from src.core.base_scraper import BaseScraper, SelectorOutdatedException
from src.core.contract import PriceContract, ProductSKU

logger = logging.getLogger(__name__)


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
            await client.goto(str(sku.product_url), wait_until="networkidle", timeout=30000)
            return await client.content()
        except Exception as e:
            logger.error("[%s] Network fetch failed for %s: %s", self.store_name, sku.product_url, e)
            return ""

    def _clean_price(self, price_str: str) -> Decimal | None:
        """Helper to convert BRL price string to Decimal."""
        if not price_str:
            return None
        # Remove R$, spaces, and periods (thousand separators)
        cleaned = re.sub(r"[R\$\s\.]", "", price_str)
        # Replace comma with period for decimal parsing
        cleaned = cleaned.replace(",", ".")
        try:
            return Decimal(cleaned)
        except Exception:
            return None

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
