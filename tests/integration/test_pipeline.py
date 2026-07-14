import os
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.contract import ProductSKU
from src.repositories.sqlite_repository import SQLitePriceRepository
from src.engine.scheduler import PriceEngine
from src.scrapers.kabum import KabumScraper
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from tests.conftest import make_gpu_model_id

def get_fixture_content(filename: str) -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    fixture_path = os.path.join(current_dir, "..", "fixtures", filename)
    with open(fixture_path, "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture
async def repo(tmp_path):
    db_path = str(tmp_path / "integration_test.db")
    repository = SQLitePriceRepository(db_path)
    await repository.initialize_schema()
    yield repository

@pytest.mark.asyncio
async def test_engine_scraper_pipeline(repo):
    """
    Tests the orchestration pipeline:
    1. Seed SKU into Repo
    2. Mock HTTP/Playwright client
    3. Run engine for scraper
    4. Assert PriceContract was parsed and saved to Repo
    """
    # 1. Seed
    gpu_model_id = await make_gpu_model_id(repo.db_path, brand="MockBrand", variant="MockModel")
    sku = ProductSKU(
        product_url="https://www.kabum.com.br/produto/123",
        store_name="kabum",
        search_keyword="rtx 5070",
        gpu_model_id=gpu_model_id,
        brand="MockBrand",
        model="MockModel",
        product_title="MockTitle"
    )
    await repo.save_skus([sku])
    
    # 2. Mock Client Factory & Client
    html_content = get_fixture_content("kabum_product_mock.html")
    mock_page = AsyncMock()
    mock_page.content.return_value = html_content
    
    mock_client_factory = MagicMock()
    mock_client_factory.create = AsyncMock(return_value=mock_page)
    mock_client_factory.close = AsyncMock()
    
    # 3. Orchestrate
    scheduler = AsyncIOScheduler()
    engine = PriceEngine(scheduler, repo, {"browser": mock_client_factory})
    
    scraper = KabumScraper()
    engine.register_scraper(scraper)
    
    await engine.run_scraper(scraper)
    
    # 4. Verify
    prices = []
    import aiosqlite
    async with aiosqlite.connect(repo.db_path) as db:
        async with db.execute("SELECT price_cash, price_installments, installment_count FROM prices") as cursor:
            prices = await cursor.fetchall()
            
    assert len(prices) == 1
    assert prices[0][0] == 5499.99
    assert prices[0][1] == 6100.00
    assert prices[0][2] == 10
    
    mock_page.goto.assert_called_once_with("https://www.kabum.com.br/produto/123", wait_until="networkidle", timeout=30000)
    mock_client_factory.close.assert_called_once()
