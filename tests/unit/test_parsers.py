import os
from decimal import Decimal

from src.scrapers.kabum import KabumScraper
from src.scrapers.terabyte import TerabyteScraper


def get_fixture_content(filename: str) -> str:
    """Helper to load HTML fixtures from disk."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fixture_path = os.path.join(base_dir, "fixtures", filename)
    with open(fixture_path, "r", encoding="utf-8") as f:
        return f.read()


def test_kabum_parser():
    """Validates the deterministic Kabum parsing logic using a static HTML fixture."""
    html_content = get_fixture_content("kabum_mock.html")
    scraper = KabumScraper()
    
    products_5070 = scraper.parse(document=html_content, keyword="rtx 5070")
    assert len(products_5070) == 1
    
    # Check first product
    p1 = products_5070[0]
    assert p1.store_name == "kabum"
    assert p1.search_keyword == "rtx 5070"
    assert p1.product_title == "Placa de Vídeo RTX 5070 12GB"
    assert str(p1.product_url) == "https://www.kabum.com.br/produto/12345/placa-de-video-rtx-5070"
    assert p1.price_cash == Decimal("5499.99")
    assert p1.price_installments == Decimal("6100.00")
    assert p1.currency == "BRL"
    assert p1.is_available is True
    assert p1.execution_id is not None
    assert p1.scraped_at is not None

    # Check Ti product
    products_ti = scraper.parse(document=html_content, keyword="rtx 5070 ti")
    assert len(products_ti) == 1
    p2 = products_ti[0]
    assert p2.product_title == "Placa de Vídeo RTX 5070 Ti 16GB"
    assert p2.price_cash == Decimal("6499.99")


def test_terabyte_parser():
    """Validates the deterministic Terabyte parsing logic using a static HTML fixture."""
    html_content = get_fixture_content("terabyte_mock.html")
    scraper = TerabyteScraper()
    
    products_5070 = scraper.parse(document=html_content, keyword="rtx 5070")
    assert len(products_5070) == 1
    
    # Check first product
    p1 = products_5070[0]
    assert p1.store_name == "terabyte"
    assert p1.search_keyword == "rtx 5070"
    assert p1.product_title == "Placa de Vídeo RTX 5070 12GB"
    assert str(p1.product_url) == "https://www.terabyteshop.com.br/produto/12345/placa-de-video-rtx-5070"
    assert p1.price_cash == Decimal("5399.90")
    assert p1.price_installments == Decimal("5999.00")
    assert p1.currency == "BRL"
    assert p1.is_available is True
    assert p1.execution_id is not None
    assert p1.scraped_at is not None

    # Check Ti product
    products_ti = scraper.parse(document=html_content, keyword="rtx 5070 ti")
    assert len(products_ti) == 1
    p2 = products_ti[0]
    assert p2.product_title == "Placa de Vídeo RTX 5070 Ti 16GB"
    assert p2.price_cash == Decimal("6399.90")
