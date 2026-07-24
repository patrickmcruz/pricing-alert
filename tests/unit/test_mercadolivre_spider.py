import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.spiders.mercadolivre import MercadoLivreSpider, _EXCLUDED_TITLE_WORDS
from src.spiders.base_spider import DiscoveredSKU


class TestMercadoLivreSpider(unittest.TestCase):

    def setUp(self):
        self.spider = MercadoLivreSpider()

    def test_spider_metadata(self):
        self.assertEqual(self.spider.store_name, "mercado-livre")
        self.assertEqual(self.spider.transport_type, "http")

    def test_excluded_title_words_contains_non_gpus(self):
        self.assertIn("notebook", _EXCLUDED_TITLE_WORDS)
        self.assertIn("laptop", _EXCLUDED_TITLE_WORDS)
        self.assertIn("waterblock", _EXCLUDED_TITLE_WORDS)
        self.assertIn("cabo", _EXCLUDED_TITLE_WORDS)
        self.assertIn("pc ", _EXCLUDED_TITLE_WORDS)

    @patch("src.spiders.mercadolivre.settings")
    def test_ensure_authenticated_success(self, mock_settings):
        mock_settings.ml_app_id = "test_app_id"
        mock_settings.ml_secret_key = "test_secret_key"

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "mock_token_123"}
        mock_client.post.return_value = mock_response

        asyncio.run(self.spider._ensure_authenticated(mock_client))
        self.assertEqual(self.spider._access_token, "mock_token_123")

    def test_fetch_search_grid_products_catalog_search(self):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "name": "Placa De Vídeo Pny Nvidia Geforce Rtx 5070 Oc 12gb",
                    "id": "MLB53508354",
                    "permalink": "https://www.mercadolivre.com.br/placa-de-video-pny-nvidia-geforce-rtx-5070-oc-12gb/p/MLB53508354"
                },
                {
                    "name": "PC Gamer Intel i9 + RTX 5070 Ti 16GB",  # Excluded prebuilt PC
                    "id": "MLB58303402",
                    "permalink": "https://www.mercadolivre.com.br/p/MLB58303402"
                }
            ]
        }
        mock_client.get.return_value = mock_response

        discovered = asyncio.run(self.spider.fetch_search_grid("rtx 5070", "gpu", mock_client))
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].product_title, "Placa De Vídeo Pny Nvidia Geforce Rtx 5070 Oc 12gb")
        self.assertEqual(discovered[0].store_name, "mercado-livre")
        self.assertEqual(discovered[0].search_keyword, "rtx 5070")

    def test_fetch_search_grid_site_search_fallback(self):
        mock_client = AsyncMock()
        
        # 1. First call (/products/search) returns 403 or empty
        mock_res_products = MagicMock()
        mock_res_products.status_code = 403

        # 2. Second call (/sites/MLB/search) returns valid item
        mock_res_sites = MagicMock()
        mock_res_sites.status_code = 200
        mock_res_sites.json.return_value = {
            "results": [
                {
                    "title": "Placa De Vídeo Sapphire Amd Radeon Rx 9070 Xt Nitro+ 16gb",
                    "permalink": "https://www.mercadolivre.com.br/placa-de-video-sapphire-amd-radeon-rx-9070-xt-nitro/p/MLB53300200"
                }
            ]
        }

        mock_client.get.side_effect = [mock_res_products, mock_res_sites]

        discovered = asyncio.run(self.spider.fetch_search_grid("rx 9070 xt", "gpu", mock_client))
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].search_keyword, "rx 9070 xt")
        self.assertIn("Sapphire Amd Radeon Rx 9070 Xt", discovered[0].product_title)


if __name__ == "__main__":
    unittest.main()
