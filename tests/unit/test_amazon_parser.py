from decimal import Decimal

import pytest

from src.core.base_scraper import SelectorOutdatedException
from src.core.contract import ProductSKU
from src.scrapers.amazon import AmazonScraper

PRICE_BLOCK = """
<div id="corePriceDisplay_desktop_feature_div">
  <div>
    <div class="a-section a-spacing-none aok-align-center aok-relative">
      <span class="a-price aok-align-center reinventPricePriceToPayMargin priceToPay apex-pricetopay-value">
        <span class="a-offscreen">R$4.799,00</span>
        <span aria-hidden="true">
          <span class="a-price-symbol">R$</span>
          <span class="a-price-whole">4.799<span class="a-price-decimal">,</span></span>
          <span class="a-price-fraction">00</span>
        </span>
      </span>
    </div>
  </div>
</div>
"""


@pytest.fixture
def scraper():
    return AmazonScraper()


@pytest.fixture
def sku():
    return ProductSKU(
        product_url="https://www.amazon.com.br/dp/B0F1XZF531",
        store_name="amazon",
        search_keyword="rtx 5070",
        produto_id="test-gpu-model-id",
        product_title="Placa de vídeo",
    )


def test_parse_raises_when_title_selector_fails(scraper, sku):
    document = f'<html><body>{PRICE_BLOCK}</body></html>'

    with pytest.raises(SelectorOutdatedException):
        scraper.parse(document, sku)


def test_parse_raises_when_price_selector_fails(scraper, sku):
    document = '<html><body><span id="productTitle">GPU</span></body></html>'

    with pytest.raises(SelectorOutdatedException):
        scraper.parse(document, sku)


def test_parse_marks_unavailable_when_out_of_stock_marker_present(scraper, sku):
    document = f"""
    <html><body>
      <span id="productTitle">GPU</span>
      {PRICE_BLOCK}
      <div>Atualmente indisponível.</div>
    </body></html>
    """

    product = scraper.parse(document, sku)

    assert product is not None
    assert product.is_available is False
    assert product.price_cash == Decimal("4799")


def test_parse_leaves_installments_none_when_selector_missing(scraper, sku):
    document = f"""
    <html><body>
      <span id="productTitle">GPU</span>
      {PRICE_BLOCK}
    </body></html>
    """

    product = scraper.parse(document, sku)

    assert product is not None
    assert product.price_installments is None
    assert product.installment_count is None


def test_parse_returns_none_for_zero_price(scraper, sku):
    document = """
    <html><body>
      <span id="productTitle">GPU</span>
      <div id="corePriceDisplay_desktop_feature_div">
        <div><div class="a-section a-spacing-none aok-align-center aok-relative">
          <span class="a-price aok-align-center reinventPricePriceToPayMargin priceToPay apex-pricetopay-value">
            <span class="a-offscreen">R$0,00</span>
            <span aria-hidden="true"><span class="a-price-whole">0</span></span>
          </span>
        </div></div>
      </div>
    </body></html>
    """

    assert scraper.parse(document, sku) is None
