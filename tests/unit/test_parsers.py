import os
from decimal import Decimal

from src.core.contract import ProductSKU
from src.scrapers.amazon import AmazonScraper
from src.scrapers.kabum import KabumScraper
from src.scrapers.terabyte import TerabyteScraper

def get_fixture_content(filename: str) -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    fixture_path = os.path.join(current_dir, "..", "fixtures", filename)
    with open(fixture_path, "r", encoding="utf-8") as f:
        return f.read()

def test_kabum_product_parser():
    """Validates the new Kabum Product Page parser."""
    html_content = get_fixture_content("kabum_product_mock.html")
    scraper = KabumScraper()
    
    sku = ProductSKU(
        store_name="kabum",
        search_keyword="rtx 5070",
        product_url="https://www.kabum.com.br/produto/123", # type: ignore
        produto_id="test-gpu-model-id",
        brand="MockBrand",
        model="MockModel",
        product_title="MockTitle"
    )
    
    product = scraper.parse(document=html_content, sku=sku)
    
    assert product is not None
    assert product.store_name == "kabum"
    assert product.search_keyword == "rtx 5070"
    assert product.brand == "MockBrand"
    assert product.model == "MockModel"
    assert product.price_cash == Decimal("5499.99")
    assert product.price_installments == Decimal("6100.00")
    assert product.installment_count == 10
    assert product.discount == Decimal("600.01")
    assert product.currency == "BRL"
    assert product.parser_version == "kabum_v2"
    assert product.is_available is True
    assert product.execution_id is not None
    assert product.scraped_at is not None


def test_kabum_parser_falls_back_to_new_price_block_layout():
    html_content = """
    <html><body>
      <h1>Placa de Vídeo MSI RTX 5070</h1>
      <div class="flex flex-col gap-4">
        <span class="text-secondary-500 font-semibold">R$ 2.999,99</span>
      </div>
      <span class="block my-12">10x de R$ 299,99</span>
      <div>Indisponível</div>
    </body></html>
    """
    scraper = KabumScraper()
    sku = ProductSKU(
        store_name="kabum",
        search_keyword="rtx 5070",
        product_url="https://www.kabum.com.br/produto/123",
        produto_id="test-gpu-model-id",
        brand="MSI",
        model="Ventus 2X",
        product_title="MockTitle",
    )

    product = scraper.parse(document=html_content, sku=sku)

    assert product is not None
    assert product.price_cash == Decimal("2999.99")
    assert product.price_installments == Decimal("2999.90")
    assert product.installment_count == 10


def test_kabum_parser_ignores_unavailable_message():
    html_content = """
    <html><body>
      <h1>Placa de Vídeo MSI RTX 5070</h1>
      <div class="flex flex-col gap-4">
        <span class="text-secondary-500 font-semibold">R$ 5.499,99</span>
      </div>
      <div>AVISE QUANDO O PRODUTO CHEGAR</div>
      <div>Não está disponível</div>
      <span class="text-secondary-500 text-xs font-bold">AVISE QUANDO O PRODUTO CHEGAR</span>
    </body></html>
    """
    scraper = KabumScraper()
    sku = ProductSKU(
        store_name="kabum",
        search_keyword="rtx 5070",
        product_url="https://www.kabum.com.br/produto/123",
        produto_id="test-gpu-model-id",
        brand="MSI",
        model="Ventus 2X",
        product_title="MockTitle",
    )

    product = scraper.parse(document=html_content, sku=sku)

    assert product is not None
    assert product.is_available is False
    assert product.price_cash == Decimal("0")
    assert product.price_installments is None


def test_terabyte_product_parser():
    """Validates the new Terabyte Product Page parser."""
    html_content = get_fixture_content("terabyte_product_mock.html")
    scraper = TerabyteScraper()
    
    sku = ProductSKU(
        store_name="terabyte",
        search_keyword="rtx 5070",
        product_url="https://www.terabyteshop.com.br/produto/123", # type: ignore
        produto_id="test-gpu-model-id",
        brand="MockBrandTB",
        model="MockModelTB",
        product_title="MockTitleTB"
    )
    
    product = scraper.parse(document=html_content, sku=sku)
    
    assert product is not None
    assert product.store_name == "terabyte"
    assert product.search_keyword == "rtx 5070"
    assert product.brand == "MockBrandTB"
    assert product.model == "MockModelTB"
    assert product.price_cash == Decimal("5399.90")
    assert product.price_installments == Decimal("5999.00")
    assert product.installment_count == 12
    assert product.discount == Decimal("599.10")
    assert product.currency == "BRL"
    assert product.parser_version == "terabyte_v1"
    assert product.is_available is True
    assert product.execution_id is not None
    assert product.scraped_at is not None


def test_amazon_product_parser():
    """Validates the Amazon.com.br product page parser."""
    html_content = get_fixture_content("amazon_product_mock.html")
    scraper = AmazonScraper()

    sku = ProductSKU(
        store_name="amazon",
        search_keyword="rtx 5070",
        product_url="https://www.amazon.com.br/INNO3D-Geforce-192BITS-GDDR7-N50702-12D7X-195064N/dp/B0F1XZF531/ref=sr_1_3",  # type: ignore
        produto_id="test-gpu-model-id",
        brand="INNO3D",
        model="TWIN X2 OC",
        product_title="MockTitleAmazon",
    )

    product = scraper.parse(document=html_content, sku=sku)

    assert product is not None
    assert product.store_name == "amazon"
    assert product.search_keyword == "rtx 5070"
    assert product.brand == "INNO3D"
    assert product.model == "TWIN X2 OC"
    assert product.price_cash == Decimal("4799")
    assert product.price_installments == Decimal("4799.88")
    assert product.installment_count == 12
    assert product.currency == "BRL"
    assert product.parser_version == "amazon_v1"
    assert product.is_available is True
    assert product.execution_id is not None
    assert product.scraped_at is not None
