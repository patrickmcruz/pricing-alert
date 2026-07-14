import pytest

from src.core.trigger import TriggerStatus
from src.db.schema import initialize_schema as initialize_db_schema
from src.repositories.sqlite_trigger_repository import SQLiteTriggerRepository


@pytest.fixture
async def repo(tmp_path):
    db_path = str(tmp_path / "trigger_test.db")
    await initialize_db_schema(db_path)
    repository = SQLiteTriggerRepository(db_path)
    yield repository


@pytest.mark.asyncio
async def test_create_request_is_pending(repo):
    request_id = await repo.create_request(store_name="kabum")

    pending = await repo.get_pending_requests()

    assert len(pending) == 1
    assert pending[0].request_id == request_id
    assert pending[0].store_name == "kabum"
    assert pending[0].status == TriggerStatus.PENDING


@pytest.mark.asyncio
async def test_create_request_with_no_store_means_all_stores(repo):
    await repo.create_request(store_name=None)

    pending = await repo.get_pending_requests()

    assert pending[0].store_name is None


@pytest.mark.asyncio
async def test_mark_processing_removes_from_pending_but_stays_active(repo):
    request_id = await repo.create_request(store_name="kabum")
    await repo.mark_processing(request_id)

    assert await repo.get_pending_requests() == []
    active = await repo.get_active_requests()
    assert len(active) == 1
    assert active[0].status == TriggerStatus.PROCESSING


@pytest.mark.asyncio
async def test_mark_completed_removes_from_active(repo):
    request_id = await repo.create_request(store_name="kabum")
    await repo.mark_processing(request_id)
    await repo.mark_completed(request_id)

    assert await repo.get_active_requests() == []


@pytest.mark.asyncio
async def test_mark_failed_records_error_and_removes_from_active(repo):
    request_id = await repo.create_request(store_name="kabum")
    await repo.mark_processing(request_id)
    await repo.mark_failed(request_id, "boom")

    assert await repo.get_active_requests() == []


@pytest.mark.asyncio
async def test_get_pending_requests_orders_oldest_first(repo):
    first_id = await repo.create_request(store_name="kabum")
    second_id = await repo.create_request(store_name="terabyte")

    pending = await repo.get_pending_requests()

    assert [r.request_id for r in pending] == [first_id, second_id]


@pytest.mark.asyncio
async def test_empty_queue_returns_empty_lists(repo):
    assert await repo.get_pending_requests() == []
    assert await repo.get_active_requests() == []


@pytest.mark.asyncio
async def test_fail_stale_processing_resolves_orphaned_requests(repo):
    # Simulates a request left 'processing' by an orchestrator process that no
    # longer exists (crash, redeploy) - nothing else would ever revisit it.
    orphaned_id = await repo.create_request(store_name="kabum")
    await repo.mark_processing(orphaned_id)

    still_pending_id = await repo.create_request(store_name="terabyte")

    count = await repo.fail_stale_processing("Orphaned: orchestrator restarted while processing")

    assert count == 1
    # The orphaned request is no longer active (failed, not pending/processing);
    # the unrelated still-pending request is untouched.
    active = await repo.get_active_requests()
    assert len(active) == 1
    assert active[0].request_id == still_pending_id
    assert active[0].status == TriggerStatus.PENDING


@pytest.mark.asyncio
async def test_fail_stale_processing_is_noop_when_nothing_processing(repo):
    await repo.create_request(store_name="kabum")

    count = await repo.fail_stale_processing("boom")

    assert count == 0
    assert len(await repo.get_pending_requests()) == 1
