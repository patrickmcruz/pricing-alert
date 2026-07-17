from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.schema import connect
from src.engine.trigger_processor import TriggerProcessor
from src.repositories.postgres_trigger_repository import PostgresTriggerRepository


async def _fetch_status_and_error(dsn: str, request_id) -> tuple[str, str | None]:
    async with connect(dsn) as db:
        row = await db.fetchrow(
            "SELECT status, error_message FROM trigger_requests WHERE id = $1",
            str(request_id),
        )
    assert row is not None
    return row["status"], row["error_message"]


def make_scraper(store_name: str) -> MagicMock:
    scraper = MagicMock()
    scraper.store_name = store_name
    return scraper


@pytest.fixture
async def repo(db_dsn):
    return PostgresTriggerRepository(db_dsn)


@pytest.fixture
def engine():
    # PriceEngine.scrapers/run_scraper are exercised elsewhere (test_engine.py) -
    # here we only care that TriggerProcessor dispatches to the right ones.
    mock_engine = MagicMock()
    mock_engine.scrapers = {
        "kabum": make_scraper("kabum"),
        "terabyte": make_scraper("terabyte"),
    }
    mock_engine.run_scraper = AsyncMock()
    return mock_engine


@pytest.mark.asyncio
async def test_process_pending_runs_all_scrapers_for_all_stores_request(repo, engine):
    await repo.create_request(store_name=None)

    processor = TriggerProcessor(repo, engine)
    await processor.process_pending()

    assert engine.run_scraper.call_count == 2
    assert await repo.get_active_requests() == []


@pytest.mark.asyncio
async def test_process_pending_runs_only_the_requested_store(repo, engine):
    await repo.create_request(store_name="kabum")

    processor = TriggerProcessor(repo, engine)
    await processor.process_pending()

    engine.run_scraper.assert_called_once_with(engine.scrapers["kabum"])


@pytest.mark.asyncio
async def test_process_pending_marks_completed_on_success(repo, engine):
    request_id = await repo.create_request(store_name="kabum")

    processor = TriggerProcessor(repo, engine)
    await processor.process_pending()

    status, error_message = await _fetch_status_and_error(repo.dsn, request_id)
    assert status == "completed"
    assert error_message is None


@pytest.mark.asyncio
async def test_process_pending_marks_failed_for_unknown_store(repo, engine):
    request_id = await repo.create_request(store_name="does-not-exist")

    processor = TriggerProcessor(repo, engine)
    await processor.process_pending()

    engine.run_scraper.assert_not_called()
    status, error_message = await _fetch_status_and_error(repo.dsn, request_id)
    assert status == "failed"
    assert error_message is not None and "does-not-exist" in error_message


@pytest.mark.asyncio
async def test_process_pending_is_noop_when_queue_is_empty(repo, engine):
    processor = TriggerProcessor(repo, engine)

    await processor.process_pending()

    engine.run_scraper.assert_not_called()


@pytest.mark.asyncio
async def test_process_pending_processes_multiple_requests(repo, engine):
    await repo.create_request(store_name="kabum")
    await repo.create_request(store_name="terabyte")

    processor = TriggerProcessor(repo, engine)
    await processor.process_pending()

    assert engine.run_scraper.call_count == 2
    assert await repo.get_active_requests() == []
