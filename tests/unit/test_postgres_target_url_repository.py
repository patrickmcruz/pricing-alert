import pytest

from src.core.contract import TargetUrlEntry
from src.repositories.postgres_target_url_repository import PostgresTargetUrlRepository


@pytest.fixture
async def repo(db_dsn):
    return PostgresTargetUrlRepository(db_dsn)


def _entry(**overrides) -> TargetUrlEntry:
    fields = {
        "store_name": "kabum",
        "search_keyword": "rtx 5070",
        "product_url": "https://www.kabum.com.br/produto/123",
        "brand": "MSI",
        "model": "Shadow 2X OC",
        "product_title": "Placa de Video MSI RTX 5070",
    }
    fields.update(overrides)
    return TargetUrlEntry(**fields)


@pytest.mark.asyncio
async def test_list_all_returns_empty_when_no_rows(repo):
    assert await repo.list_all() == []


@pytest.mark.asyncio
async def test_upsert_many_inserts_new_rows(repo):
    inserted = await repo.upsert_many([_entry(), _entry(product_url="https://www.kabum.com.br/produto/456")])

    assert inserted == 2
    rows = await repo.list_all()
    assert len(rows) == 2
    assert {r.product_url for r in rows} == {
        "https://www.kabum.com.br/produto/123",
        "https://www.kabum.com.br/produto/456",
    }


@pytest.mark.asyncio
async def test_upsert_many_ignores_existing_product_urls(repo):
    await repo.upsert_many([_entry(brand="MSI")])

    inserted = await repo.upsert_many([_entry(brand="Zotac")])  # same product_url, different brand

    assert inserted == 0
    rows = await repo.list_all()
    assert len(rows) == 1
    assert rows[0].brand == "MSI"  # first-seen row wins, not overwritten


@pytest.mark.asyncio
async def test_upsert_many_with_empty_list_is_a_noop(repo):
    assert await repo.upsert_many([]) == 0


@pytest.mark.asyncio
async def test_list_all_preserves_optional_fields(repo):
    await repo.upsert_many([_entry(brand=None, model=None, product_title=None)])

    rows = await repo.list_all()

    assert rows[0].brand is None
    assert rows[0].model is None
    assert rows[0].product_title is None
