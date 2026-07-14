import pytest
import aiosqlite
from decimal import Decimal
from datetime import datetime, timezone
import uuid

from src.core.contract import PriceContract, ProductSKU
from src.repositories.sqlite_repository import SQLitePriceRepository

@pytest.fixture
async def repo(tmp_path):
    # Use a file-based temporary database so we can open new connections to verify data
    db_path = str(tmp_path / "test.db")
    repository = SQLitePriceRepository(db_path)
    await repository.initialize_schema()
    yield repository

@pytest.mark.asyncio
async def test_repository_save_target_urls(repo):
    sku = ProductSKU(
        product_url="https://example.com/gpu",
        store_name="example",
        search_keyword="rtx 5070",
        brand="Nvidia",
        model="Founders",
        product_title="RTX 5070"
    )
    await repo.save_skus([sku])
    
    urls = await repo.get_target_skus("example")
    assert len(urls) == 1
    assert str(urls[0].product_url) == "https://example.com/gpu"
    assert urls[0].store_name == "example"

@pytest.mark.asyncio
async def test_repository_save_prices(repo):
    contract = PriceContract(
        execution_id=uuid.uuid4(),
        store_name="example",
        search_keyword="rtx 5070",
        product_title="RTX 5070",
        product_url="https://example.com/gpu",
        price_cash=Decimal("5000.00"),
        price_installments=Decimal("5500.00"),
        installment_count=10,
        currency="BRL",
        parser_version="v1",
        is_available=True,
        scraped_at=datetime.now(timezone.utc)
    )
    
    await repo.save_prices([contract])

    # Query directly to verify
    async with aiosqlite.connect(repo.db_path) as db:
        async with db.execute("SELECT price_cash, price_installments, installment_count FROM prices") as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 5000.00
            assert row[1] == 5500.00
            assert row[2] == 10


@pytest.mark.asyncio
async def test_repository_get_prices_by_keyword(repo):
    contract = PriceContract(
        store_name="example",
        search_keyword="rtx 5070",
        product_title="RTX 5070",
        product_url="https://example.com/gpu",
        price_cash=Decimal("5000.00"),
        currency="BRL",
        parser_version="v1",
        is_available=True,
    )
    other_keyword = contract.model_copy(update={"search_keyword": "rtx 5080", "product_url": "https://example.com/other"})

    await repo.save_prices([contract, other_keyword])

    results = await repo.get_prices_by_keyword("rtx 5070")

    assert len(results) == 1
    assert results[0].search_keyword == "rtx 5070"
    assert results[0].price_cash == Decimal("5000.00")


@pytest.mark.asyncio
async def test_repository_get_prices_by_keyword_no_matches(repo):
    results = await repo.get_prices_by_keyword("does-not-exist")
    assert results == []

