import pytest

from src.core.execution import RunStatus
from src.repositories.sqlite_execution_repository import SQLiteExecutionRepository


@pytest.fixture
async def repo(tmp_path):
    db_path = str(tmp_path / "execution_test.db")
    repository = SQLiteExecutionRepository(db_path)
    await repository.initialize_schema()
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
        run_id, RunStatus.SUCCESS, skus_total=5, skus_succeeded=4, skus_failed=1
    )

    latest = await repo.get_latest_runs()

    assert latest[0].status == RunStatus.SUCCESS
    assert latest[0].finished_at is not None
    assert latest[0].skus_total == 5
    assert latest[0].skus_succeeded == 4
    assert latest[0].skus_failed == 1
    assert latest[0].error_message is None


@pytest.mark.asyncio
async def test_finish_run_records_error_message_on_failure(repo):
    run_id = await repo.start_run("mercado-livre")

    await repo.finish_run(
        run_id,
        RunStatus.FAILED,
        skus_total=0,
        skus_succeeded=0,
        skus_failed=0,
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
