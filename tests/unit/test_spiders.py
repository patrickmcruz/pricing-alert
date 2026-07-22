import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from src.spiders.base_spider import BaseSpider, DiscoveredSKU
from src.spiders.mercadolivre import MercadoLivreSpider
from src.spiders.registry import get_registered_spiders, register_spider, get_spider_class


class TestSpiderArchitecture(unittest.TestCase):

    def test_discovered_sku_contract(self):
        sku = DiscoveredSKU(
            store_name="mercado-livre",
            search_keyword="ryzen 7 9800x3d",
            product_url="https://produto.mercadolivre.com.br/MLB-12345",
            product_title="Processador AMD Ryzen 7 9800X3D AM5",
            category="cpu",
        )
        self.assertEqual(sku.store_name, "mercado-livre")
        self.assertEqual(sku.search_keyword, "ryzen 7 9800x3d")
        self.assertEqual(sku.category, "cpu")

    def test_spider_registry(self):
        spiders = get_registered_spiders()
        self.assertIn("mercado-livre", spiders)
        self.assertIn("pichau", spiders)
        self.assertIn("kabum", spiders)

        cls = get_spider_class("mercado-livre")
        self.assertEqual(cls, MercadoLivreSpider)

    def test_mercadolivre_spider_mock_rest_api(self):
        spider = MercadoLivreSpider()
        self.assertEqual(spider.transport_type, "http")

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "permalink": "https://produto.mercadolivre.com.br/MLB-9999",
                    "title": "Processador AMD Ryzen 7 9800X3D 8-Core AM5 Box",
                }
            ]
        }
        mock_client.get.return_value = mock_response

        discovered = asyncio.run(spider.execute("ryzen 7 9800x3d", category="cpu", client=mock_client))
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].product_url, "https://produto.mercadolivre.com.br/MLB-9999")
        self.assertEqual(discovered[0].product_title, "Processador AMD Ryzen 7 9800X3D 8-Core AM5 Box")


if __name__ == "__main__":
    unittest.main()
