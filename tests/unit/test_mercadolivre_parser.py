import os
import json
from decimal import Decimal

import pytest

from src.core.contract import ProductSKU
from src.scrapers.mercadolivre import MercadoLivreScraper


@pytest.fixture
def scraper():
    s = MercadoLivreScraper()
    return s


@pytest.fixture
def sample_sku():
    return ProductSKU(
        product_url="https://produto.mercadolivre.com.br/MLB-53508354-placa-de-video",
        store_name="mercado-livre",
        search_keyword="rtx 5070",
        brand="PNY",
        model="rtx 5070",
        product_title="Placa de vídeo Pny Nvidia Geforce Rtx 5070 Oc",
    )


@pytest.fixture
def valid_json():
    data = {
        "id_type": "item",
        "data": {
            "id": "MLB53508354",
            "title": "Placa de vídeo Pny Nvidia Geforce Rtx 5070 Oc",
            "price": 4500.99,
            "currency_id": "BRL",
            "available_quantity": 5,
            "status": "active",
            "listing_type_id": "gold_pro"
        }
    }
    return json.dumps(data)


@pytest.fixture
def out_of_stock_json():
    data = {
        "error": "not_found"
    }
    return json.dumps(data)


def test_mercadolivre_parser_success(scraper, sample_sku, valid_json):
    contract = scraper.parse(valid_json, sample_sku)

    assert contract is not None
    assert contract.store_name == "mercado-livre"
    assert contract.price_cash == Decimal("4500.99")
    assert contract.price_installments == Decimal("4500.99")
    assert contract.installment_count == 10
    assert contract.brand == "PNY"
    assert contract.is_available is True
    assert contract.currency == "BRL"


def test_mercadolivre_parser_out_of_stock(scraper, sample_sku, out_of_stock_json):
    contract = scraper.parse(out_of_stock_json, sample_sku)

    assert contract is not None
    assert contract.store_name == "mercado-livre"
    assert contract.is_available is False
    assert contract.price_cash == Decimal(0)
