import pytest
from unittest.mock import AsyncMock, MagicMock
from src.engine.discovery import DiscoveryEngine
from src.core.contract import ProductSKU, StoreConfig
from src.repositories.base_repository import PriceRepository

@pytest.mark.asyncio
async def test_discovery_engine_run():
    # Setup mocks
    mock_repo = AsyncMock(spec=PriceRepository)
    mock_spider = AsyncMock()
    mock_spider.store_name = "mock_store"
    mock_spider.search_keywords = ["keyword"]
    
    sku = ProductSKU(
        product_url="http://mock.com/1",
        store_name="mock_store",
        search_keyword="keyword",
        brand="MockBrand",
        model="MockModel",
        product_title="Mock Product"
    )
    mock_spider.discover = AsyncMock(return_value=[sku])
    
    # Mock client factory
    mock_client = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.create = AsyncMock(return_value=mock_client)
    mock_factory.close = AsyncMock()
    
    engine = DiscoveryEngine(mock_repo, mock_factory)
    engine.register_spider(mock_spider)
    
    config = StoreConfig(
        store_name="mock_store",
        cron_times=["12:00"],
        target_keywords=["keyword"]
    )
    await engine.run_discovery([config])
    
    # Verify behavior
    mock_factory.create.assert_called_once()
    mock_spider.discover.assert_called_once_with("keyword", mock_client)
    mock_repo.save_skus.assert_called_once_with([sku])
    mock_factory.close.assert_called_once_with(mock_client)
