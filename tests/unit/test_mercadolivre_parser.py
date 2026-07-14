import json
from decimal import Decimal

import pytest

from src.core.contract import ProductSKU
from src.scrapers.mercadolivre import MercadoLivreScraper


@pytest.fixture
def scraper():
    return MercadoLivreScraper()


@pytest.fixture
def catalog_sku():
    return ProductSKU(
        product_url="https://produto.mercadolivre.com.br/p/MLB53508354",
        store_name="mercado-livre",
        search_keyword="rtx 5070",
        brand="PNY",
        model="rtx 5070",
        product_title="Placa de vídeo Pny Nvidia Geforce Rtx 5070 Oc",
    )


@pytest.fixture
def item_sku():
    return ProductSKU(
        product_url="https://produto.mercadolivre.com.br/MLB-53508354-placa-de-video",
        store_name="mercado-livre",
        search_keyword="rtx 5070",
        brand="PNY",
        model="rtx 5070",
        product_title="Placa de vídeo Pny Nvidia Geforce Rtx 5070 Oc",
    )


def test_extract_id_from_catalog_url(scraper):
    assert scraper._extract_id_from_url("https://produto.mercadolivre.com.br/p/MLB53508354") == "MLB53508354"


def test_extract_id_from_item_url(scraper):
    assert scraper._extract_id_from_url("https://produto.mercadolivre.com.br/MLB-53508354-placa-de-video") == "MLB53508354"


def test_parse_catalog_picks_lowest_cash_and_gold_pro_installment_price(scraper, catalog_sku):
    document = json.dumps(
        {
            "type": "catalog",
            "product": {"name": "Placa de vídeo Pny Nvidia Geforce Rtx 5070 Oc"},
            "items": [
                {"price": 4599.00, "listing_type_id": "gold_special"},
                {"price": 4500.00, "listing_type_id": "gold_pro"},
                {"price": 4800.00, "listing_type_id": "gold_pro"},
            ],
        }
    )

    contract = scraper.parse(document, catalog_sku)

    assert contract is not None
    assert contract.store_name == "mercado-livre"
    assert contract.price_cash == Decimal("4500.00")
    assert contract.price_installments == Decimal("4500.00")
    assert contract.installment_count == 10
    assert contract.is_available is True
    assert contract.parser_version == "mercado-livre_api_v1"
    assert contract.currency == "BRL"


def test_parse_catalog_with_no_items_is_unavailable(scraper, catalog_sku):
    document = json.dumps({"type": "catalog", "product": {"name": "Some GPU"}, "items": []})

    contract = scraper.parse(document, catalog_sku)

    assert contract is not None
    assert contract.is_available is False
    assert contract.price_cash == Decimal("0")


def test_parse_item_gold_pro_listing(scraper, item_sku):
    document = json.dumps(
        {
            "type": "item",
            "item": {
                "title": "Placa de vídeo Pny Nvidia Geforce Rtx 5070 Oc",
                "status": "active",
                "available_quantity": 5,
                "price": 4700.00,
                "listing_type_id": "gold_pro",
            },
        }
    )

    contract = scraper.parse(document, item_sku)

    assert contract is not None
    assert contract.price_cash == Decimal("4700.00")
    assert contract.installment_count == 10
    assert contract.is_available is True


def test_parse_item_inactive_is_unavailable(scraper, item_sku):
    document = json.dumps(
        {
            "type": "item",
            "item": {
                "title": "Placa de vídeo Pny Nvidia Geforce Rtx 5070 Oc",
                "status": "paused",
                "available_quantity": 0,
                "price": 4700.00,
            },
        }
    )

    contract = scraper.parse(document, item_sku)

    assert contract is not None
    assert contract.is_available is False
    assert contract.price_cash == Decimal("0")


def test_parse_invalid_json_returns_none(scraper, item_sku):
    assert scraper.parse("not-json", item_sku) is None


def test_parse_empty_document_returns_none(scraper, item_sku):
    assert scraper.parse("", item_sku) is None
