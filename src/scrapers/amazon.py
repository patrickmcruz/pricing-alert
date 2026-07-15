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
from src.core.utils import simulate_human_interaction

logger = logging.getLogger(__name__)

# Amazon's installment string reads e.g. "Em até 12x R$ 399,99 sem juros".
_INSTALLMENT_RE = re.compile(r"(\d+)\s*x\s*R\$\s*([\d.,]+)", re.IGNORECASE)


@register_scraper
class AmazonScraper(BaseScraper):
    """
    Scraper implementation for Amazon.com.br - direct product-page HTML
    scraping via Playwright.

    SP-API's Product Pricing API would be the "official" route, but reaching
    it for real (non-sandbox) prices requires production self-authorization
    against an active Seller Central seller account, which this project
    doesn't have - see src/scrapers/amazon_spapi.py for that dormant path.
    """

    def __init__(self):
        super().__init__(store_name="amazon", base_url="https://www.amazon.com.br")

    async def fetch(self, sku: ProductSKU, client: Any) -> str:
        """
        Retrieves the raw HTML document from the store using Playwright.
        """
        try:
            await client.goto(
                str(sku.product_url), wait_until="domcontentloaded", timeout=settings.navigation_timeout_ms
            )
            await simulate_human_interaction(client)
            return await client.content()
        except Exception as e:
            logger.error("[%s] Network fetch failed for %s: %s", self.store_name, sku.product_url, e)
            return ""

    def parse(self, document: str, sku: ProductSKU) -> Optional[PriceContract]:
        """
        Parses the Amazon product page.
        """
        parser_version = "v1"
        selectors = self.load_selectors(parser_version)
        soup = BeautifulSoup(document, "lxml")

        title_elem = soup.select_one(selectors["title"])
        if not title_elem:
            raise SelectorOutdatedException(f"[{self.store_name}] Title selector '{selectors['title']}' failed.")
        title = title_elem.text.strip()

        price_cash_elem = soup.select_one(selectors["price_cash"])
        if not price_cash_elem:
            raise SelectorOutdatedException(
                f"[{self.store_name}] Cash price selector '{selectors['price_cash']}' failed."
            )

        price_cash_str = price_cash_elem.text.strip()
        price_cash = clean_brl_price(price_cash_str)
        if price_cash is None or price_cash <= 0:
            return None

        is_available = not has_out_of_stock_marker(soup, selectors["out_of_stock"])

        price_installments = None
        installment_count = None
        inst_elem = soup.select_one(selectors["price_installments"]) if "price_installments" in selectors else None
        if inst_elem:
            match = _INSTALLMENT_RE.search(inst_elem.text.strip())
            if match:
                installment_count = int(match.group(1))
                monthly_price = clean_brl_price(match.group(2))
                if monthly_price:
                    price_installments = monthly_price * installment_count

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
