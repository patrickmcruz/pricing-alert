import pytest
import aiosqlite
from decimal import Decimal
from datetime import datetime, timezone
import uuid

from src.core.contract import PriceContract, ProductSKU
from src.db.schema import initialize_schema as initialize_db_schema
from src.repositories.sqlite_repository import SQLitePriceRepository

from tests.conftest import make_gpu_model_id

@pytest.fixture
async def repo(tmp_path):
    # Use a file-based temporary database so we can open new connections to verify data
    db_path = str(tmp_path / "test.db")
    await initialize_db_schema(db_path)
    repository = SQLitePriceRepository(db_path)
    yield repository

@pytest.mark.asyncio
async def test_repository_save_target_urls(repo):
    gpu_model_id = await make_gpu_model_id(repo.db_path, brand="Nvidia", variant="Founders")
    sku = ProductSKU(
        product_url="https://example.com/gpu",
        store_name="example",
        search_keyword="rtx 5070",
        gpu_model_id=gpu_model_id,
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
async def test_repository_list_all_skus(repo):
    kabum_gpu_model_id = await make_gpu_model_id(repo.db_path, brand="Nvidia", variant="Founders")
    terabyte_gpu_model_id = await make_gpu_model_id(
        repo.db_path, brand="MSI", chipset="rtx 5070 ti", variant="Gaming Trio"
    )
    kabum_sku = ProductSKU(
        product_url="https://example.com/kabum-gpu",
        store_name="kabum",
        search_keyword="rtx 5070",
        gpu_model_id=kabum_gpu_model_id,
        brand="Nvidia",
        model="Founders",
        product_title="RTX 5070 Kabum",
    )
    terabyte_sku = ProductSKU(
        product_url="https://example.com/terabyte-gpu",
        store_name="terabyte",
        search_keyword="rtx 5070 ti",
        gpu_model_id=terabyte_gpu_model_id,
        brand="MSI",
        model="Gaming Trio",
        product_title="RTX 5070 Ti Terabyte",
    )
    await repo.save_skus([kabum_sku, terabyte_sku])

    all_skus = await repo.list_all_skus()

    assert len(all_skus) == 2
    assert {sku.store_name for sku in all_skus} == {"kabum", "terabyte"}


@pytest.mark.asyncio
async def test_repository_delete_sku(repo):
    gpu_model_id = await make_gpu_model_id(repo.db_path, brand="Nvidia", variant="Founders")
    sku = ProductSKU(
        product_url="https://example.com/gpu-to-delete",
        store_name="example",
        search_keyword="rtx 5070",
        gpu_model_id=gpu_model_id,
        brand="Nvidia",
        model="Founders",
        product_title="RTX 5070",
    )
    await repo.save_skus([sku])

    await repo.delete_sku("https://example.com/gpu-to-delete")

    assert await repo.list_all_skus() == []
    assert await repo.get_target_skus("example") == []


@pytest.mark.asyncio
async def test_repository_delete_sku_missing_url_is_noop(repo):
    await repo.delete_sku("https://example.com/does-not-exist")
    assert await repo.list_all_skus() == []


@pytest.mark.asyncio
async def test_repository_save_prices(repo):
    gpu_model_id = await make_gpu_model_id(repo.db_path, brand="Nvidia", variant="Founders")
    sku = ProductSKU(
        product_url="https://example.com/gpu",
        store_name="example",
        search_keyword="rtx 5070",
        gpu_model_id=gpu_model_id,
        brand="Nvidia",
        model="Founders",
        product_title="RTX 5070",
    )
    await repo.save_skus([sku])

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

    observation_ids = await repo.save_prices([contract])
    assert len(observation_ids) == 1

    # Query directly to verify
    async with aiosqlite.connect(repo.db_path) as db:
        async with db.execute(
            "SELECT price_cash, price_installments, installment_count FROM price_observations"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 5000.00
            assert row[1] == 5500.00
            assert row[2] == 10


@pytest.mark.asyncio
async def test_repository_save_prices_raises_for_untracked_listing(repo):
    contract = PriceContract(
        store_name="example",
        search_keyword="rtx 5070",
        product_title="RTX 5070",
        product_url="https://example.com/untracked-gpu",
        price_cash=Decimal("5000.00"),
        currency="BRL",
        parser_version="v1",
        is_available=True,
    )

    with pytest.raises(ValueError):
        await repo.save_prices([contract])


@pytest.mark.asyncio
async def test_repository_get_prices_by_keyword(repo):
    gpu_model_id = await make_gpu_model_id(repo.db_path, brand="Nvidia", variant="Founders")
    other_gpu_model_id = await make_gpu_model_id(
        repo.db_path, brand="Nvidia", chipset="rtx 5080", variant="Founders"
    )
    await repo.save_skus(
        [
            ProductSKU(
                product_url="https://example.com/gpu",
                store_name="example",
                search_keyword="rtx 5070",
                gpu_model_id=gpu_model_id,
                brand="Nvidia",
                model="Founders",
                product_title="RTX 5070",
            ),
            ProductSKU(
                product_url="https://example.com/other",
                store_name="example",
                search_keyword="rtx 5080",
                gpu_model_id=other_gpu_model_id,
                brand="Nvidia",
                model="Founders",
                product_title="RTX 5080",
            ),
        ]
    )

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
