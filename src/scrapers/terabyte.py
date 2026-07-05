import logging
import re
from decimal import Decimal
from typing import Any, List

from bs4 import BeautifulSoup
from pydantic import ValidationError

from src.core.base_scraper import BaseScraper
from src.core.contract import PriceContract

logger = logging.getLogger(__name__)


class TerabyteScraper(BaseScraper):
    """
    Scraper implementation for Terabyteshop.
    """

    def __init__(self):
        super().__init__(
            store_name="terabyte", base_url="https://www.terabyteshop.com.br"
        )

    async def fetch(self, keyword: str, client: Any) -> str:
        """
        Retrieves the raw HTML document from the store.
        """
        raise NotImplementedError("Network fetch is not implemented yet.")

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

    def parse(self, document: str, keyword: str) -> List[PriceContract]:
        """
        Parses Terabyte HTML to extract products.
        """
        soup = BeautifulSoup(document, "lxml")
        products = []

        cards = soup.find_all("div", class_="pbox")
        for card in cards:
            try:
                link_elem = card.find("a")
                if not link_elem or not link_elem.get("href"):
                    continue
                url = str(link_elem.get("href"))

                title_elem = card.find(class_="prod-name")
                title = title_elem.text.strip() if title_elem else "Unknown"
                
                title_lower = title.lower()
                keyword_lower = keyword.lower()
                
                # Strict filtering to differentiate RTX 5070 from RTX 5070 Ti
                if "5070 ti" in keyword_lower and "ti" not in title_lower:
                    continue
                elif "5070" in keyword_lower and "ti" not in keyword_lower and "ti" in title_lower:
                    continue

                price_cash_elem = card.find(class_="prod-new-price")
                price_cash_str = price_cash_elem.text.strip() if price_cash_elem else ""
                price_cash = self._clean_price(price_cash_str)

                if price_cash is None:
                    continue

                price_inst_elem = card.find(class_="prod-juros")
                price_inst_str = price_inst_elem.text.strip() if price_inst_elem else ""
                price_inst = self._clean_price(price_inst_str)

                is_available = True

                contract = PriceContract(
                    store_name=self.store_name,
                    search_keyword=keyword,
                    product_title=title,
                    product_url=url,  # type: ignore
                    price_cash=price_cash,
                    price_installments=price_inst,
                    is_available=is_available,
                )
                products.append(contract)
            except ValidationError as e:
                logger.warning(
                    "Failed to validate product on %s: %s", self.store_name, e
                )
            except Exception as e:
                logger.error("Error parsing product card on %s: %s", self.store_name, e)

        return products
