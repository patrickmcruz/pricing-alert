import pytest

from src.core.execution import RunStatus, SkuRunStatus
from src.db.schema import initialize_schema as initialize_db_schema
from src.repositories.sqlite_execution_repository import SQLiteExecutionRepository


@pytest.fixture
async def repo(tmp_path):
    db_path = str(tmp_path / "execution_test.db")
    await initialize_db_schema(db_path)
    repository = SQLiteExecutionRepository(db_path)
    yield repository


@pytest.mark.asyncio
async def test_start_run_records_running_state(repo):
    run_id = await repo.start_run("kabum")

    latest = await repo.get_latest_runs()

    assert len(latest) == 1
    assert latest[0].run_id == run_id
    assert latest[0].store_name == "kabum"
    assert latest[0].status == RunStatus.RUNNING
    assert latest[0].finished_at is None


@pytest.mark.asyncio
async def test_finish_run_updates_status_and_counters(repo):
    run_id = await repo.start_run("kabum")

    await repo.finish_run(
        run_id, RunStatus.SUCCESS, listings_total=5, listings_succeeded=4, listings_failed=1
    )

    latest = await repo.get_latest_runs()

    assert latest[0].status == RunStatus.SUCCESS
    assert latest[0].finished_at is not None
    assert latest[0].listings_total == 5
    assert latest[0].listings_succeeded == 4
    assert latest[0].listings_failed == 1
    assert latest[0].error_message is None


@pytest.mark.asyncio
async def test_finish_run_records_error_message_on_failure(repo):
    run_id = await repo.start_run("mercado-livre")

    await repo.finish_run(
        run_id,
        RunStatus.FAILED,
        listings_total=0,
        listings_succeeded=0,
        listings_failed=0,
        error_message="boom",
    )

    latest = await repo.get_latest_runs()

    assert latest[0].status == RunStatus.FAILED
    assert latest[0].error_message == "boom"


@pytest.mark.asyncio
async def test_get_latest_runs_returns_newest_per_store(repo):
    first_run_id = await repo.start_run("kabum")
    await repo.finish_run(first_run_id, RunStatus.SUCCESS, 1, 1, 0)

    second_run_id = await repo.start_run("kabum")
    await repo.finish_run(second_run_id, RunStatus.FAILED, 1, 0, 1, error_message="retry failed")

    latest = await repo.get_latest_runs()

    assert len(latest) == 1
    assert latest[0].run_id == second_run_id
    assert latest[0].status == RunStatus.FAILED


@pytest.mark.asyncio
async def test_get_latest_runs_returns_one_entry_per_distinct_store(repo):
    await repo.start_run("kabum")
    await repo.start_run("terabyte")

    latest = await repo.get_latest_runs()

    assert {r.store_name for r in latest} == {"kabum", "terabyte"}


@pytest.mark.asyncio
async def test_get_run_history_orders_newest_first_and_respects_limit(repo):
    for store in ["kabum", "terabyte", "mercado-livre"]:
        run_id = await repo.start_run(store)
        await repo.finish_run(run_id, RunStatus.SUCCESS, 1, 1, 0)

    history = await repo.get_run_history(limit=2)

    assert len(history) == 2
    assert history[0].store_name == "mercado-livre"
    assert history[1].store_name == "terabyte"


@pytest.mark.asyncio
async def test_get_latest_runs_empty_when_nothing_ran(repo):
    assert await repo.get_latest_runs() == []
    assert await repo.get_run_history() == []


@pytest.mark.asyncio
async def test_fail_stale_running_runs_marks_running_rows_as_failed(repo):
    stuck_run_id = await repo.start_run("terabyte")

    count = await repo.fail_stale_running_runs("Orphaned: orchestrator restarted while running")

    assert count == 1
    latest = await repo.get_latest_runs()
    assert latest[0].run_id == stuck_run_id
    assert latest[0].status == RunStatus.FAILED
    assert latest[0].finished_at is not None
    assert latest[0].error_message == "Orphaned: orchestrator restarted while running"


@pytest.mark.asyncio
async def test_fail_stale_running_runs_leaves_finished_runs_untouched(repo):
    run_id = await repo.start_run("kabum")
    await repo.finish_run(run_id, RunStatus.SUCCESS, listings_total=1, listings_succeeded=1, listings_failed=0)

    count = await repo.fail_stale_running_runs("Orphaned: orchestrator restarted while running")

    assert count == 0
    latest = await repo.get_latest_runs()
    assert latest[0].status == RunStatus.SUCCESS


@pytest.mark.asyncio
async def test_fail_stale_running_runs_returns_zero_when_nothing_running(repo):
    assert await repo.fail_stale_running_runs("boom") == 0


@pytest.mark.asyncio
async def test_start_sku_run_records_running_state(repo):
    run_id = await repo.start_run("kabum")

    sku_run_id = await repo.start_sku_run(run_id, "kabum", "https://example.com/gpu", "RTX 5070")

    current = await repo.get_current_sku_run(run_id)
    assert current is not None
    assert current.sku_run_id == sku_run_id
    assert current.run_id == run_id
    assert current.store_name == "kabum"
    assert current.product_url == "https://example.com/gpu"
    assert current.product_title == "RTX 5070"
    assert current.status == SkuRunStatus.RUNNING
    assert current.finished_at is None


@pytest.mark.asyncio
async def test_finish_sku_run_updates_status_and_clears_current(repo):
    run_id = await repo.start_run("kabum")
    sku_run_id = await repo.start_sku_run(run_id, "kabum", "https://example.com/gpu", "RTX 5070")

    await repo.finish_sku_run(sku_run_id, SkuRunStatus.SUCCESS)

    assert await repo.get_current_sku_run(run_id) is None
    counts = await repo.get_sku_run_counts(run_id)
    assert counts == {SkuRunStatus.SUCCESS: 1}


@pytest.mark.asyncio
async def test_finish_sku_run_records_error_message(repo):
    run_id = await repo.start_run("kabum")
    sku_run_id = await repo.start_sku_run(run_id, "kabum", "https://example.com/gpu", "RTX 5070")

    await repo.finish_sku_run(sku_run_id, SkuRunStatus.TIMEOUT, "Timed out after 120s")

    counts = await repo.get_sku_run_counts(run_id)
    assert counts == {SkuRunStatus.TIMEOUT: 1}


@pytest.mark.asyncio
async def test_get_current_sku_run_returns_none_when_nothing_running(repo):
    run_id = await repo.start_run("kabum")
    assert await repo.get_current_sku_run(run_id) is None

    sku_run_id = await repo.start_sku_run(run_id, "kabum", "https://example.com/gpu", "RTX 5070")
    await repo.finish_sku_run(sku_run_id, SkuRunStatus.SUCCESS)

    assert await repo.get_current_sku_run(run_id) is None


@pytest.mark.asyncio
async def test_get_sku_run_counts_groups_by_status(repo):
    run_id = await repo.start_run("kabum")

    ok = await repo.start_sku_run(run_id, "kabum", "https://example.com/1", "GPU 1")
    await repo.finish_sku_run(ok, SkuRunStatus.SUCCESS)

    failed = await repo.start_sku_run(run_id, "kabum", "https://example.com/2", "GPU 2")
    await repo.finish_sku_run(failed, SkuRunStatus.TIMEOUT)

    still_running = await repo.start_sku_run(run_id, "kabum", "https://example.com/3", "GPU 3")

    counts = await repo.get_sku_run_counts(run_id)

    assert counts == {
        SkuRunStatus.SUCCESS: 1,
        SkuRunStatus.TIMEOUT: 1,
        SkuRunStatus.RUNNING: 1,
    }
    current = await repo.get_current_sku_run(run_id)
    assert current is not None
    assert current.sku_run_id == still_running


@pytest.mark.asyncio
async def test_get_sku_run_counts_empty_for_unknown_run(repo):
    run_id = await repo.start_run("kabum")
    assert await repo.get_sku_run_counts(run_id) == {}


@pytest.mark.asyncio
async def test_fail_stale_running_sku_runs_marks_running_rows_as_failed(repo):
    run_id = await repo.start_run("terabyte")
    stuck_sku_run_id = await repo.start_sku_run(run_id, "terabyte", "https://example.com/gpu", "RTX 5070")

    count = await repo.fail_stale_running_sku_runs("Orphaned: orchestrator restarted while running")

    assert count == 1
    assert await repo.get_current_sku_run(run_id) is None
    counts = await repo.get_sku_run_counts(run_id)
    assert counts == {SkuRunStatus.FAILED: 1}
    assert stuck_sku_run_id is not None  # sanity: the id we started is the one that got reset


@pytest.mark.asyncio
async def test_fail_stale_running_sku_runs_leaves_finished_rows_untouched(repo):
    run_id = await repo.start_run("kabum")
    sku_run_id = await repo.start_sku_run(run_id, "kabum", "https://example.com/gpu", "RTX 5070")
    await repo.finish_sku_run(sku_run_id, SkuRunStatus.SUCCESS)

    count = await repo.fail_stale_running_sku_runs("boom")

    assert count == 0
    counts = await repo.get_sku_run_counts(run_id)
    assert counts == {SkuRunStatus.SUCCESS: 1}


@pytest.mark.asyncio
async def test_fail_stale_running_sku_runs_returns_zero_when_nothing_running(repo):
    assert await repo.fail_stale_running_sku_runs("boom") == 0
