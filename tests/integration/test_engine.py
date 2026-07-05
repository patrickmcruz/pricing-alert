import pytest
from unittest.mock import AsyncMock, MagicMock

from typing import Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.base_scraper import BaseScraper
from src.core.contract import PriceContract, StoreConfig
from src.engine.scheduler import PriceEngine
from src.repositories.base_repository import PriceRepository


class MockScraper(BaseScraper):
    def __init__(self, store_name):
        super().__init__(store_name=store_name, base_url="http://mock")
        self.execute_mock = AsyncMock(return_value=[])

    async def fetch(self, keyword: str, client: Any) -> str:
        return ""

    def parse(self, document: str, keyword: str) -> list[PriceContract]:
        return []

    async def execute(self, keyword: str, client: Any) -> list[PriceContract]:
        return await self.execute_mock(keyword, client)


@pytest.fixture
def mock_repository():
    repo = MagicMock(spec=PriceRepository)
    repo.save_prices = AsyncMock()
    return repo


@pytest.fixture
def mock_client_factory():
    factory = MagicMock()
    factory.create = AsyncMock(return_value="mock_client")
    factory.close = AsyncMock()
    return factory


@pytest.fixture
def engine(mock_repository, mock_client_factory):
    scheduler = AsyncIOScheduler()
    return PriceEngine(scheduler, mock_repository, mock_client_factory)


@pytest.mark.asyncio
async def test_engine_run_scraper(engine, mock_repository, mock_client_factory):
    scraper = MockScraper("mock_store")

    # Simulate scraper returning some mock prices
    mock_price = MagicMock(spec=PriceContract)
    scraper.execute_mock.return_value = [mock_price]

    keywords = ["rtx 5070", "rtx 5070 ti"]

    await engine.run_scraper(scraper, keywords)

    # Verify client factory was called
    mock_client_factory.create.assert_called_once_with(scraper)
    mock_client_factory.close.assert_called_once_with("mock_client")

    # Verify scraper was executed for each keyword
    assert scraper.execute_mock.call_count == 2
    scraper.execute_mock.assert_any_call("rtx 5070", "mock_client")
    scraper.execute_mock.assert_any_call("rtx 5070 ti", "mock_client")

    # Verify repository was called to save prices for each keyword
    assert mock_repository.save_prices.call_count == 2
    mock_repository.save_prices.assert_any_call([mock_price])


def test_engine_build_schedule(engine):
    scraper = MockScraper("mock_store")
    engine.register_scraper(scraper)

    config = StoreConfig(
        store_name="mock_store",
        target_keywords=["rtx 5070"],
        cron_times=["08:30", "15:45"],
    )

    engine.build_schedule([config])

    jobs = engine.scheduler.get_jobs()
    assert len(jobs) == 2

    # Apscheduler stores cron triggers, we can check their fields
    job1_trigger = jobs[0].trigger
    assert str(job1_trigger.fields[5]) == "8"  # hour
    assert str(job1_trigger.fields[6]) == "30"  # minute

    job2_trigger = jobs[1].trigger
    assert str(job2_trigger.fields[5]) == "15"  # hour
    assert str(job2_trigger.fields[6]) == "45"  # minute
