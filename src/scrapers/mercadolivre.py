import logging
import re
from decimal import Decimal
from typing import Any, Optional
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.core.base_scraper import BaseScraper, SelectorOutdatedException
from src.core.contract import PriceContract, ProductSKU

logger = logging.getLogger(__name__)

class MercadoLivreScraper(BaseScraper):
    """
    Scraper implementation for Mercado Livre using HTML and CSS Selectors.
    """

    def __init__(self):
        super().__init__(store_name="mercado-livre", base_url="https://www.mercadolivre.com.br")

    async def fetch(self, sku: ProductSKU, client: Any) -> str:
        """
        Retrieves the raw HTML document from the store using Playwright.
        """
        try:
            # client is a Playwright Page object here
            await client.goto(str(sku.product_url), wait_until="domcontentloaded", timeout=30000)
            return await client.content()
        except Exception as e:
            logger.error("[%s] Network fetch failed for %s: %s", self.store_name, sku.product_url, e)
            return ""

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

    def parse(self, document: str, sku: ProductSKU) -> Optional[PriceContract]:
        """
        Parses the Mercado Livre product page.
        """
        if not document:
            return None
            
        parser_version = "v2"
        try:
            selectors = self.load_selectors(parser_version)
        except Exception:
            # Fallback if toml fails
            selectors = {
                "price_cash": {"price_container": ".ui-pdp-price__second-line .andes-money-amount__fraction"},
                "price_installments": {
                    "installment_text": "#_R_98rcj2aj4tlpa_ > span.andes-money-amount__fraction",
                    "installment_count": "#pricing_price_subtitle > span:nth-child(4)",
                    "fallback_subtitle": "#pricing_price_subtitle"
                },
                "out_of_stock": {"text": "Estoque indisponível"}
            }
            
        soup = BeautifulSoup(document, "lxml")

        # 1. Title
        title_elem = soup.select_one("h1.ui-pdp-title")
        title = title_elem.text.strip() if title_elem else sku.product_title

        # 2. Availability
        is_available = True
        out_of_stock_text = selectors.get("out_of_stock", {}).get("text", "Estoque indisponível")
        if soup.find(string=re.compile(out_of_stock_text, re.I)):
            is_available = False

        if not is_available:
            return self._build_unavailable_contract(sku)

        # 3. Cash Price
        price_cash_sel = selectors.get("price_cash", {}).get("price_container", ".ui-pdp-price__second-line .andes-money-amount__fraction")
        price_cash_elem = soup.select_one(price_cash_sel)
        
        if not price_cash_elem:
            raise SelectorOutdatedException(f"[{self.store_name}] Cash price selector '{price_cash_sel}' failed.")
            
        price_cash = self._clean_price(price_cash_elem.text.strip())
        if price_cash is None or price_cash <= 0:
            return self._build_unavailable_contract(sku)

        # 4. Installments
        inst_sel_text = selectors.get("price_installments", {}).get("installment_text", "#_R_98rcj2aj4tlpa_ > span.andes-money-amount__fraction")
        inst_sel_count = selectors.get("price_installments", {}).get("installment_count", "#pricing_price_subtitle > span:nth-child(4)")
        
        price_installments = None
        installment_count = None
        
        # Parse installment price
        inst_price_elem = soup.select_one(inst_sel_text)
        if inst_price_elem:
            price_installments = self._clean_price(inst_price_elem.text.strip())
            
        # Parse installment count
        inst_count_elem = soup.select_one(inst_sel_count)
        if inst_count_elem:
            count_text = inst_count_elem.text.strip()
            # Find the number in text like "10x" or just "10"
            match = re.search(r'(\d+)', count_text)
            if match:
                installment_count = int(match.group(1))

        # If installment price found but no count, fallback to 1
        if price_installments and not installment_count:
            installment_count = 1
            
        # --- Fallback Logic ---
        # If the specific dynamic ID for the installment price was missing,
        # we can try to extract the count and individual value from the fallback block
        # Format example: "18x R$ 266 , 61 sem juros"
        if not price_installments:
            fallback_sel = selectors.get("price_installments", {}).get("fallback_subtitle", "#pricing_price_subtitle")
            # We look for the main subtitle block
            subtitle_block = soup.select_one(fallback_sel)
            if subtitle_block:
                block_text = subtitle_block.text
                # Match e.g., "18x" and "R$ 266 , 61"
                match = re.search(r'(\d+)\s*x.*?R\$?\s*([\d\s\.,]+)', block_text, re.IGNORECASE)
                if match:
                    extracted_count = int(match.group(1))
                    extracted_val_str = match.group(2).strip()
                    
                    per_installment = self._clean_price(extracted_val_str)
                    if per_installment:
                        installment_count = extracted_count
                        price_installments = extracted_count * per_installment

        # ML Rule: If still no installment info is found, it usually means 1x at cash price
        if not price_installments:
            price_installments = price_cash
            installment_count = 1

        discount = None
        if price_installments and price_installments > 0 and price_cash > 0:
            discount = price_installments - price_cash

        return PriceContract(
            store_name=self.store_name,
            search_keyword=sku.search_keyword,
            product_title=title,
            product_url=sku.product_url,
            price_cash=price_cash,
            price_installments=price_installments,
            installment_count=installment_count,
            currency="BRL",
            parser_version=f"{self.store_name}_{parser_version}_html",
            is_available=is_available,
            brand=sku.brand,
            model=sku.model,
            discount=discount
        )

    def _build_unavailable_contract(self, sku: ProductSKU) -> PriceContract:
        return PriceContract(
            product_url=sku.product_url,
            store_name=self.store_name,
            search_keyword=sku.search_keyword,
            brand=sku.brand,
            model=sku.model,
            product_title=sku.product_title,
            price_cash=Decimal(0),
            price_installments=Decimal(0),
            installment_count=0,
            scraped_at=datetime.now(timezone.utc),
            parser_version="v2_html",
            currency="BRL",
            is_available=False,
        )
