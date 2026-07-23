"""
Parser tests against synthetic fixture HTML that reproduces the real shape
of pichau.com.br pages: a Next.js RSC payload (`self.__next_f.push(...)`)
embedding the GraphQL product JSON, confirmed against the live site (no
longer down for maintenance - see specs/pichau-scraper/spec.md §4) via a
direct HTTP fetch during this store's onboarding.
"""
import json
from decimal import Decimal

import pytest

from src.core.base_scraper import SelectorOutdatedException, StoreUnavailableException
from src.core.contract import ProductSKU
from src.scrapers.pichau import PichauScraper

PRODUCT_URL = "https://www.pichau.com.br/placa-de-video-msi-geforce-rtx-5070-ti-16gb"
URL_KEY = "placa-de-video-msi-geforce-rtx-5070-ti-16gb"


def _product(**overrides) -> dict:
    product = {
        "id": 1,
        "sku": "MSI-5070TI-16G",
        "name": "MSI GeForce RTX 5070 Ti 16GB",
        "url_key": URL_KEY,
        "marcas_info": {"name": "MSI"},
        "pichau_prices": {
            "avista": 4799.00,
            "avista_discount": 15,
            "avista_method": "PIX",
            "base_price": 5599.00,
            "final_price": 5299.00,
            "max_installments": 12,
        },
        "stock_status": "IN_STOCK",
    }
    product.update(overrides)
    return product


def _page(*products: dict, title: str = "Placa de Video MSI GeForce RTX 5070 Ti 16GB | Pichau") -> str:
    inner = json.dumps({"products": {"items": list(products)}}, separators=(",", ":"))
    push_arg = json.dumps([1, f"6:{inner}\n"], separators=(",", ":"))
    return f"<html><head><title>{title}</title></head><body><script>self.__next_f.push({push_arg})</script></body></html>"


@pytest.fixture
def scraper():
    return PichauScraper()


@pytest.fixture
def sku():
    return ProductSKU(
        product_url=PRODUCT_URL,
        store_name="pichau",
        search_keyword="rtx 5070 ti",
        produto_id="test-gpu-model-id",
        product_title="Placa de vídeo",
    )


def test_parse_raises_when_no_product_json_found(scraper, sku):
    document = "<html><head><title>Placa de Video | Pichau</title></head><body>no data here</body></html>"

    with pytest.raises(SelectorOutdatedException):
        scraper.parse(document, sku)


def test_parse_raises_store_unavailable_for_a_maintenance_page(scraper, sku):
    # The actual failure mode pichau.com.br was in while this store was first
    # scoped (see specs/pichau-scraper/spec.md §4) - a maintenance page has
    # no embedded product JSON either, so this confirms the maintenance
    # check wins and reports the real cause instead of a misleading
    # SelectorOutdatedException.
    document = "<html><head><title>Site em Manutenção - Pichau</title></head><body></body></html>"

    with pytest.raises(StoreUnavailableException):
        scraper.parse(document, sku)


def test_parse_extracts_price_and_title(scraper, sku):
    document = _page(_product())

    product = scraper.parse(document, sku)

    assert product is not None
    assert product.product_title == "MSI GeForce RTX 5070 Ti 16GB"
    assert product.price_cash == Decimal("4799.00")
    assert product.price_installments == Decimal("5599.00")
    assert product.installment_count == 12
    assert product.is_available is True
    assert product.parser_version == "pichau_v2"
    assert product.discount == Decimal("800.00")


def test_parse_marks_unavailable_when_stock_status_is_not_in_stock(scraper, sku):
    document = _page(_product(stock_status="OUT_OF_STOCK"))

    product = scraper.parse(document, sku)

    assert product is not None
    assert product.is_available is False
    assert product.price_cash == Decimal("0.00")


def test_parse_returns_none_for_zero_price(scraper, sku):
    document = _page(_product(pichau_prices={
        "avista": 0, "avista_discount": 0, "avista_method": "PIX",
        "base_price": 0, "final_price": 0, "max_installments": 1,
    }))

    product = scraper.parse(document, sku)
    assert product is not None
    assert product.is_available is False
    assert product.price_cash == Decimal("0.00")


def test_parse_matches_product_by_url_key_when_page_lists_several(scraper, sku):
    # Real search-result pages embed many products; a product page should
    # only ever have one, but parse() must pick the one matching the SKU's
    # own URL rather than assuming it's first.
    document = _page(
        _product(sku="OTHER-SKU", url_key="some-other-product", name="Some Other Card"),
        _product(),
    )

    product = scraper.parse(document, sku)

    assert product is not None
    assert product.product_title == "MSI GeForce RTX 5070 Ti 16GB"
