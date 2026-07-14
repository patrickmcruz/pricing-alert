from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from src.core.contract import PriceContract, ProductSKU

if TYPE_CHECKING:
    from src.core.base_scraper import BaseScraper


def build_price_contract(
    scraper: "BaseScraper",
    sku: ProductSKU,
    *,
    price_cash: Decimal,
    product_title: str,
    parser_version: str,
    is_available: bool = True,
    price_installments: Decimal | None = None,
    installment_count: int | None = None,
    discount: Decimal | None = None,
    currency: str = "BRL",
) -> PriceContract:
    """Builds a PriceContract, prefilling the fields every scraper derives from itself/the SKU."""
    return PriceContract(
        store_name=scraper.store_name,
        search_keyword=sku.search_keyword,
        product_title=product_title,
        product_url=sku.product_url,
        price_cash=price_cash,
        price_installments=price_installments if price_installments and price_installments > 0 else None,
        installment_count=installment_count,
        currency=currency,
        parser_version=parser_version,
        is_available=is_available,
        brand=sku.brand,
        model=sku.model,
        discount=discount,
    )


def build_unavailable_contract(
    scraper: "BaseScraper",
    sku: ProductSKU,
    *,
    parser_version: str,
    product_title: str | None = None,
) -> PriceContract:
    """Builds the standard 'product is unavailable' PriceContract."""
    return build_price_contract(
        scraper,
        sku,
        price_cash=Decimal("0"),
        product_title=product_title or sku.product_title,
        parser_version=parser_version,
        is_available=False,
    )
