import logging
import re
from typing import Any, Optional

from bs4.element import Tag

from bs4 import BeautifulSoup

from src.core.base_scraper import BaseScraper, SelectorOutdatedException
from src.core.config import settings
from src.core.contract import PriceContract, ProductSKU
from src.core.contract_factory import build_price_contract, build_unavailable_contract
from src.core.parsing_utils import clean_brl_price, compute_discount, has_out_of_stock_marker
from src.core.registry import register_scraper

logger = logging.getLogger(__name__)


def _extract_price_from_candidates(soup: BeautifulSoup, selectors: list[str]) -> Optional[str]:
    def _is_price_text(text: str) -> bool:
        if not text:
            return False
        if re.search(r"(indisponível|não está disponível|avise quando o produto chegar|avise quando o produto estiver disponível)", text, re.I):
            return False
        # Exclude monthly installment strings like "10x de R$ 1.167,82" from being parsed as cash price
        if re.search(r"(\d+\s*x\s*de|\d+\s*x\s*R\$)", text, re.I):
            return False
        return bool(re.search(r"R\$\s*([\d.,]+)", text))

    for selector in selectors:
        elem = soup.select_one(selector)
        if elem is None:
            continue
        text = elem.get_text(" ", strip=True)
        if _is_price_text(text):
            match = re.search(r"R\$\s*([\d.,]+)", text)
            if match:
                return match.group(0)

    for elem in soup.find_all(string=re.compile(r"R\$\s*[\d.,]+")):
        if isinstance(elem, str):
            if _is_price_text(elem):
                match = re.search(r"R\$\s*([\d.,]+)", elem)
                if match:
                    return match.group(0)

    for elem in soup.find_all():
        if not isinstance(elem, Tag):
            continue
        text = elem.get_text(" ", strip=True)
        if _is_price_text(text) and len(text) < 140:
            match = re.search(r"R\$\s*([\d.,]+)", text)
            if match:
                return match.group(0)

    return None


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
            # client is a Playwright Page object here. Use domcontentloaded instead of
            # networkidle to avoid hanging on background analytics/tracking connections.
            await client.goto(
                str(sku.product_url), wait_until="domcontentloaded", timeout=settings.navigation_timeout_ms
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

        is_available = not has_out_of_stock_marker(soup, selectors["out_of_stock"])
        if not is_available:
            return build_unavailable_contract(self, sku, parser_version=parser_version, product_title=title)

        # Scope extraction to main product container wrapper to avoid carousel/cross-sell recommended items
        main_container = None
        if title_elem:
            curr = title_elem.parent
            for _ in range(5):
                if curr and (curr.get("id") or "product" in " ".join(curr.get("class", [])) or curr.name == "main"):
                    main_container = curr
                    break
                if curr and curr.parent:
                    curr = curr.parent
        target_scope = main_container or soup

        price_cash_str = _extract_price_from_candidates(
            target_scope,
            [selectors["price_cash"], "h4.text-4xl", "h4[class*='text-secondary-500']", "h4[class*='finalPrice']", ".finalPrice"],
        )
        if not price_cash_str:
            raise SelectorOutdatedException(f"[{self.store_name}] Cash price selector '{selectors['price_cash']}' failed.")

        price_cash = clean_brl_price(price_cash_str)
        if price_cash is None or price_cash <= 0:
            return None

        price_inst_elem = soup.select_one(selectors["price_installments"])
        price_inst_str = price_inst_elem.text.strip() if price_inst_elem else ""
        price_installments = clean_brl_price(price_inst_str)

        if price_installments is None and price_inst_elem is not None:
            installment_match = re.search(r"(\d+)x\s+de\s+R\$\s*([\d.,]+)", price_inst_elem.get_text(" ", strip=True), re.IGNORECASE)
            if installment_match:
                monthly_price = clean_brl_price(installment_match.group(2))
                installment_count = int(installment_match.group(1))
                if monthly_price is not None:
                    price_installments = monthly_price

        if price_installments is None:
            installment_match = re.search(r"(\d+)x\s+de\s+R\$\s*([\d.,]+)", document, re.IGNORECASE)
            if installment_match:
                monthly_price = clean_brl_price(installment_match.group(2))
                installment_count = int(installment_match.group(1))
                if monthly_price is not None:
                    price_installments = monthly_price

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

        # Sanity check: Reject cash prices that are unreasonably low or extracted from monthly installments
        if price_installments and price_cash:
            from decimal import Decimal
            if price_cash < (price_installments / Decimal("3")):
                logger.warning("[%s] Cash price R$%s is suspiciously low compared to installment total R$%s. Rejecting anomaly.", self.store_name, price_cash, price_installments)
                return None

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
