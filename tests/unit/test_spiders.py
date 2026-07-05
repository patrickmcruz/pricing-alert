import os

from src.spiders.kabum_spider import KabumSpider
from src.spiders.terabyte_spider import TerabyteSpider

def get_fixture_content(filename: str) -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    fixture_path = os.path.join(current_dir, "..", "fixtures", filename)
    with open(fixture_path, "r", encoding="utf-8") as f:
        return f.read()

def test_kabum_spider_parse_grid():
    html_content = get_fixture_content("kabum_mock.html")
    spider = KabumSpider()
    
    skus = spider.parse_search_grid(html_content, "rtx 5070")
    
    # Grid should contain the 2 mocked products
    assert len(skus) == 2
    
    p1 = skus[0]
    assert p1.product_title == "Placa de Vídeo RTX 5070 12GB"
    assert str(p1.product_url) == "https://www.kabum.com.br/produto/12345/placa-de-video-rtx-5070"
    assert p1.search_keyword == "rtx 5070"

def test_terabyte_spider_parse_grid():
    html_content = get_fixture_content("terabyte_mock.html")
    spider = TerabyteSpider()
    
    skus = spider.parse_search_grid(html_content, "rtx 5070")
    
    assert len(skus) == 2
    
    p1 = skus[0]
    assert p1.product_title == "Placa de Vídeo RTX 5070 12GB"
    assert str(p1.product_url) == "https://www.terabyteshop.com.br/produto/12345/placa-de-video-rtx-5070"
    assert p1.search_keyword == "rtx 5070"
