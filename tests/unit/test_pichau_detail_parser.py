import json
from decimal import Decimal

import pytest

from src.core.base_scraper import StoreUnavailableException
from src.core.contract import ProductSKU
from src.scrapers.pichau import PichauScraper


def _sku() -> ProductSKU:
    return ProductSKU(
        product_url="https://www.pichau.com.br/placa-de-video-msi-geforce-rtx-5070-ti-16gb",
        store_name="pichau",
        search_keyword="rtx 5070 ti",
        produto_id="test-gpu-model-id",
        product_title="Placa de vídeo",
    )


def _product_payload() -> dict:
    return {
        "id": 1,
        "sku": "MSI-5070TI-16G",
        "name": "MSI GeForce RTX 5070 Ti 16GB",
        "url_key": "placa-de-video-msi-geforce-rtx-5070-ti-16gb",
        "marcas_info": {"name": "MSI"},
        "pichau_prices": {
            "avista": 4799.00,
            "base_price": 5599.00,
            "max_installments": 12,
        },
        "stock_status": "IN_STOCK",
        "brand": "MSI",
        "short_description": "Placa de vídeo MSI",
        "description": "Descrição detalhada da placa",
        "specifications": [
            {"name": "Memória", "value": "16GB"},
            {"name": "Modelo", "value": "Gaming X Trio"},
        ],
    }


def test_parse_extracts_extended_details_from_embedded_product_json():
    scraper = PichauScraper()
    payload = json.dumps({"products": {"items": [_product_payload()]}}, separators=(",", ":"))
    push_arg = json.dumps([1, f"6:{payload}\n"], separators=(",", ":"))
    document = f"<html><body><script>self.__next_f.push({push_arg})</script></body></html>"

    contract = scraper.parse(document, _sku())

    assert contract is not None
    assert contract.product_title == "MSI GeForce RTX 5070 Ti 16GB"
    assert contract.price_cash == Decimal("4799.00")
    assert contract.price_installments == Decimal("5599.00")
    assert contract.installment_count == 12
    assert contract.is_available is True
    assert contract.brand == "MSI"
    assert contract.model == "Gaming X Trio"


def test_parse_prefers_dom_installment_values_when_available():
    scraper = PichauScraper()
    payload = json.dumps({"products": {"items": [_product_payload()]}}, separators=(",", ":"))
    push_arg = json.dumps([1, f"6:{payload}\n"], separators=(",", ":"))
    document = (
        "<html><body><script>self.__next_f.push(" + push_arg + ")</script>"
        "<div id='main-content'><div class='MuiContainer-root'>"
        "<div class='mui-caclr-sectionWrapperHorizontal-extraSpace'>"
        "<div><div><div class='mui-7ie9un-price_total'>R$ 2.499,99</div><span>12x</span></div></div>"
        "</div></div></div></body></html>"
    )

    contract = scraper.parse(document, _sku())

    assert contract is not None
    assert contract.price_installments == Decimal("2499.99")
    assert contract.installment_count == 12


def test_parse_raises_store_unavailable_for_maintenance_page():
    scraper = PichauScraper()
    document = "<html><body><h1>Site em Manutenção</h1><p>Voltamos em breve.</p></body></html>"

    with pytest.raises(StoreUnavailableException):
        scraper.parse(document, _sku())
