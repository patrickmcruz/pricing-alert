import os
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
def valid_html():
    return """
    <html>
        <body>
            <h1 class="ui-pdp-title">Placa de vídeo Pny Nvidia Geforce Rtx 5070 Oc</h1>
            <div class="ui-pdp-price__second-line">
                <span class="andes-money-amount__fraction">4.500</span>
            </div>
            <div id="_R_98rcj2aj4tlpa_">
                <span class="andes-money-amount__fraction">450</span>
            </div>
            <div id="pricing_price_subtitle">
                <span></span><span></span><span></span><span>10x</span>
            </div>
        </body>
    </html>
    """

@pytest.fixture
def fallback_html():
    return """
    <html>
        <body>
            <h1 class="ui-pdp-title">Placa de vídeo Pny Nvidia Geforce Rtx 5070 Oc</h1>
            <div class="ui-pdp-price__second-line">
                <span class="andes-money-amount__fraction">4.500</span>
            </div>
            <!-- Missing #_R_98rcj2aj4tlpa_ entirely -->
            <div id="pricing_price_subtitle">
                <span>18x </span><span>R$ </span><span>266 </span><span>, </span><span>61 </span><span> sem juros</span>
            </div>
        </body>
    </html>
    """

@pytest.fixture
def out_of_stock_html():
    return """
    <html>
        <body>
            <h1 class="ui-pdp-title">Placa de vídeo Pny Nvidia Geforce Rtx 5070 Oc</h1>
            <div>Estoque indisponível</div>
        </body>
    </html>
    """

def test_mercadolivre_parser_success(scraper, sample_sku, valid_html):
    # Mocking the load_selectors so it doesn't try to read TOML during tests if not needed
    def mock_load_selectors(version):
        return {
            "price_cash": {"price_container": ".ui-pdp-price__second-line .andes-money-amount__fraction"},
            "price_installments": {
                "installment_text": "#_R_98rcj2aj4tlpa_ > span.andes-money-amount__fraction",
                "installment_count": "#pricing_price_subtitle > span:nth-child(4)"
            },
            "out_of_stock": {"text": "Estoque indisponível"}
        }
    scraper.load_selectors = mock_load_selectors

    contract = scraper.parse(valid_html, sample_sku)

    assert contract is not None
    assert contract.store_name == "mercado-livre"
    assert contract.price_cash == Decimal("4500.00")
    assert contract.price_installments == Decimal("450.00")
    assert contract.installment_count == 10
    assert contract.brand == "PNY"
    assert contract.is_available is True
    assert contract.currency == "BRL"

def test_mercadolivre_parser_out_of_stock(scraper, sample_sku, out_of_stock_html):
    def mock_load_selectors(version):
        return {
            "price_cash": {"price_container": ".ui-pdp-price__second-line .andes-money-amount__fraction"},
            "price_installments": {
                "installment_text": "#_R_98rcj2aj4tlpa_ > span.andes-money-amount__fraction",
                "installment_count": "#pricing_price_subtitle > span:nth-child(4)",
                "fallback_subtitle": "#pricing_price_subtitle"
            },
            "out_of_stock": {"text": "Estoque indisponível"}
        }
    scraper.load_selectors = mock_load_selectors

    contract = scraper.parse(out_of_stock_html, sample_sku)

    assert contract is not None
    assert contract.store_name == "mercado-livre"
    assert contract.is_available is False
    assert contract.price_cash == Decimal(0)

def test_mercadolivre_parser_fallback(scraper, sample_sku, fallback_html):
    def mock_load_selectors(version):
        return {
            "price_cash": {"price_container": ".ui-pdp-price__second-line .andes-money-amount__fraction"},
            "price_installments": {
                "installment_text": "#_R_98rcj2aj4tlpa_ > span.andes-money-amount__fraction",
                "installment_count": "#pricing_price_subtitle > span:nth-child(4)"
            },
            "out_of_stock": {"text": "Estoque indisponível"}
        }
    scraper.load_selectors = mock_load_selectors

    contract = scraper.parse(fallback_html, sample_sku)

    assert contract is not None
    assert contract.store_name == "mercado-livre"
    assert contract.price_cash == Decimal("4500.00")
    # 18 * 266.61 = 4798.98
    assert contract.price_installments == Decimal("4798.98")
    assert contract.installment_count == 18
    assert contract.brand == "PNY"
    assert contract.is_available is True
    assert contract.currency == "BRL"
