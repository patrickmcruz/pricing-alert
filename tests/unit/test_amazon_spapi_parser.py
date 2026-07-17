import json
from decimal import Decimal

import pytest

from src.core.contract import ProductSKU
from src.scrapers.amazon_spapi import AmazonSPAPIScraper


@pytest.fixture
def scraper():
    return AmazonSPAPIScraper()


@pytest.fixture
def sku():
    return ProductSKU(
        product_url="https://www.amazon.com.br/dp/B0DXXXXXXX",
        store_name="amazon",
        search_keyword="rtx 5070",
        produto_id="test-gpu-model-id",
        product_title="Placa de vídeo",
    )


def test_parse_returns_none_for_empty_document(scraper, sku):
    assert scraper.parse("", sku) is None


def test_parse_returns_none_for_invalid_json(scraper, sku):
    assert scraper.parse("not-json", sku) is None


def test_parse_returns_unavailable_contract_when_no_offers(scraper, sku):
    document = json.dumps({"payload": {"Offers": []}})

    contract = scraper.parse(document, sku)

    assert contract is not None
    assert contract.is_available is False
    assert contract.price_cash == Decimal("0")


def test_parse_picks_lowest_landed_price_across_offers(scraper, sku):
    document = json.dumps(
        {
            "payload": {
                "Offers": [
                    {
                        "ListingPrice": {"Amount": 4500.00, "CurrencyCode": "BRL"},
                        "Shipping": {"Amount": 0.00, "CurrencyCode": "BRL"},
                    },
                    {
                        "ListingPrice": {"Amount": 4300.00, "CurrencyCode": "BRL"},
                        "Shipping": {"Amount": 50.00, "CurrencyCode": "BRL"},
                    },
                ]
            }
        }
    )

    contract = scraper.parse(document, sku)

    assert contract is not None
    assert contract.is_available is True
    assert contract.price_cash == Decimal("4350.00")
    assert contract.product_title == "Placa de vídeo"
    assert contract.parser_version == "amazon_spapi_v1"


def test_parse_ignores_offers_missing_listing_price(scraper, sku):
    document = json.dumps(
        {
            "payload": {
                "Offers": [
                    {"Shipping": {"Amount": 0.00, "CurrencyCode": "BRL"}},
                    {
                        "ListingPrice": {"Amount": 4300.00, "CurrencyCode": "BRL"},
                        "Shipping": {"Amount": 0.00, "CurrencyCode": "BRL"},
                    },
                ]
            }
        }
    )

    contract = scraper.parse(document, sku)

    assert contract is not None
    assert contract.price_cash == Decimal("4300.00")


def test_parse_returns_unavailable_when_all_offers_missing_listing_price(scraper, sku):
    document = json.dumps({"payload": {"Offers": [{"Shipping": {"Amount": 0.00, "CurrencyCode": "BRL"}}]}})

    contract = scraper.parse(document, sku)

    assert contract is not None
    assert contract.is_available is False
