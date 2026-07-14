import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

from typing import Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.base_scraper import BaseScraper
from src.core.contract import PriceContract, StoreConfig, ProductSKU
from src.core.execution import RunStatus
from src.engine import scheduler as scheduler_module
from src.engine.scheduler import PriceEngine, MissingScraperError
from src.repositories.base_repository import PriceRepository
from src.repositories.execution_repository import ExecutionRepository


def make_price_contract(**overrides) -> PriceContract:
    defaults: dict[str, Any] = dict(
        store_name="mock_store",
        search_keyword="rtx 5070",
        product_title="Mock Product",
        product_url="https://mock.example.com/product",
        price_cash=Decimal("1000.00"),
        currency="BRL",
        parser_version="mock_v1",
        is_available=True,
    )
    defaults.update(overrides)
    return PriceContract(**defaults)  # type: ignore[arg-type]


class MockScraper(BaseScraper):
    def __init__(self, store_name):
        super().__init__(store_name=store_name, base_url="http://mock")
        self.execute_mock = AsyncMock(return_value=[])

    async def fetch(self, sku: ProductSKU, client: Any) -> str:
        return "mock_html"

    def parse(self, document: str, sku: ProductSKU) -> Optional[PriceContract]:
        return None

    async def execute(self, sku: ProductSKU, client: Any) -> Optional[PriceContract]:
        return await self.execute_mock(sku, client)


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
    return PriceEngine(scheduler, mock_repository, {"browser": mock_client_factory})


@pytest.fixture
def mock_execution_repository():
    repo = AsyncMock(spec=ExecutionRepository)
    repo.start_run.return_value = uuid4()
    return repo


@pytest.fixture
def engine_with_tracking(mock_repository, mock_client_factory, mock_execution_repository):
    scheduler = AsyncIOScheduler()
    return PriceEngine(
        scheduler,
        mock_repository,
        {"browser": mock_client_factory},
        execution_repository=mock_execution_repository,
    )


@pytest.mark.asyncio
async def test_engine_run_scraper(engine, mock_repository, mock_client_factory):
    scraper = MockScraper("mock_store")

    # Simulate scraper returning some mock prices
    mock_price = make_price_contract()
    scraper.execute_mock.return_value = mock_price

    mock_sku = MagicMock(spec=ProductSKU)
    mock_sku.product_url = "https://mock"
    mock_repository.get_target_skus.return_value = [mock_sku]

    await engine.run_scraper(scraper)

    # Verify client factory was called
    mock_client_factory.create.assert_called_once_with(scraper)
    mock_client_factory.close.assert_called_once_with("mock_client")


    # Verify scraper was executed
    scraper.execute_mock.assert_called_once()

    # Verify repository was called to save prices
    assert mock_repository.save_prices.call_count == 1
    mock_repository.save_prices.assert_any_call([mock_price])


@pytest.mark.asyncio
async def test_engine_run_scraper_times_out_a_hung_sku_instead_of_blocking_forever(
    engine_with_tracking, mock_repository, mock_execution_repository, monkeypatch
):
    # A hung page must not block the whole run - src/engine/scheduler.py wraps
    # scraper.execute() in asyncio.wait_for(timeout=settings.scraper_timeout_seconds).
    monkeypatch.setattr(scheduler_module.settings, "scraper_timeout_seconds", 0.05)

    scraper = MockScraper("mock_store")

    async def hang(*args, **kwargs):
        await asyncio.sleep(10)

    scraper.execute_mock.side_effect = hang

    mock_sku = MagicMock(spec=ProductSKU)
    mock_sku.product_url = "https://mock"
    mock_repository.get_target_skus.return_value = [mock_sku]

    # The overall test itself times out (failing loudly) if the watchdog doesn't work.
    await asyncio.wait_for(engine_with_tracking.run_scraper(scraper), timeout=5)

    mock_repository.save_prices.assert_not_called()
    mock_execution_repository.finish_run.assert_called_once()
    call = mock_execution_repository.finish_run.call_args
    assert call.args[1] == RunStatus.SUCCESS
    assert call.kwargs["skus_total"] == 1
    assert call.kwargs["skus_succeeded"] == 0
    assert call.kwargs["skus_failed"] == 1


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


def test_engine_build_schedule_skips_disabled_store_without_scraper(engine):
    config = StoreConfig(
        store_name="unregistered_store",
        cron_times=["08:00"],
        enabled=False,
    )

    # Should not raise - disabled stores are allowed to have no scraper.
    engine.build_schedule([config])
    assert engine.scheduler.get_jobs() == []


def test_engine_build_schedule_raises_for_enabled_store_without_scraper(engine):
    config = StoreConfig(
        store_name="unregistered_store",
        cron_times=["08:00"],
        enabled=True,
    )

    with pytest.raises(MissingScraperError):
        engine.build_schedule([config])


@pytest.mark.asyncio
async def test_engine_run_scraper_records_successful_execution(
    engine_with_tracking, mock_repository, mock_execution_repository
):
    scraper = MockScraper("mock_store")
    mock_price = make_price_contract()
    scraper.execute_mock.return_value = mock_price

    mock_sku = MagicMock(spec=ProductSKU)
    mock_sku.product_url = "https://mock"
    mock_repository.get_target_skus.return_value = [mock_sku]

    await engine_with_tracking.run_scraper(scraper)

    mock_execution_repository.start_run.assert_called_once_with("mock_store")
    mock_execution_repository.finish_run.assert_called_once()
    call = mock_execution_repository.finish_run.call_args
    assert call.args[1] == RunStatus.SUCCESS
    assert call.kwargs["skus_total"] == 1
    assert call.kwargs["skus_succeeded"] == 1
    assert call.kwargs["skus_failed"] == 0
    assert call.kwargs["error_message"] is None


@pytest.mark.asyncio
async def test_engine_run_scraper_records_failed_execution_on_client_error(
    engine_with_tracking, mock_repository, mock_client_factory, mock_execution_repository
):
    scraper = MockScraper("mock_store")
    mock_sku = MagicMock(spec=ProductSKU)
    mock_sku.product_url = "https://mock"
    mock_repository.get_target_skus.return_value = [mock_sku]
    mock_client_factory.create.side_effect = RuntimeError("boom")

    await engine_with_tracking.run_scraper(scraper)

    mock_execution_repository.finish_run.assert_called_once()
    call = mock_execution_repository.finish_run.call_args
    assert call.args[1] == RunStatus.FAILED
    assert call.kwargs["error_message"] == "boom"


@pytest.mark.asyncio
async def test_engine_run_scraper_records_success_with_zero_skus(
    engine_with_tracking, mock_repository, mock_execution_repository
):
    mock_repository.get_target_skus.return_value = []
    scraper = MockScraper("mock_store")

    await engine_with_tracking.run_scraper(scraper)

    mock_execution_repository.start_run.assert_called_once_with("mock_store")
    call = mock_execution_repository.finish_run.call_args
    assert call.args[1] == RunStatus.SUCCESS
    assert call.kwargs["skus_total"] == 0
