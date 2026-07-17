import pytest
from decimal import Decimal
from datetime import datetime, timezone
import uuid

from src.core.contract import PriceContract, ProductSKU
from src.db.schema import connect
from src.repositories.postgres_repository import PostgresPriceRepository

from tests.conftest import make_produto_id

@pytest.fixture
async def repo(db_dsn):
    return PostgresPriceRepository(db_dsn)

@pytest.mark.asyncio
async def test_repository_save_target_urls(repo):
    produto_id = await make_produto_id(repo.dsn, brand="Nvidia", variant="Founders")
    sku = ProductSKU(
        product_url="https://example.com/gpu",
        store_name="example",
        search_keyword="rtx 5070",
        produto_id=produto_id,
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
    kabum_produto_id = await make_produto_id(repo.dsn, brand="Nvidia", variant="Founders")
    terabyte_produto_id = await make_produto_id(
        repo.dsn, brand="MSI", chipset="rtx 5070 ti", variant="Gaming Trio"
    )
    kabum_sku = ProductSKU(
        product_url="https://example.com/kabum-gpu",
        store_name="kabum",
        search_keyword="rtx 5070",
        produto_id=kabum_produto_id,
        brand="Nvidia",
        model="Founders",
        product_title="RTX 5070 Kabum",
    )
    terabyte_sku = ProductSKU(
        product_url="https://example.com/terabyte-gpu",
        store_name="terabyte",
        search_keyword="rtx 5070 ti",
        produto_id=terabyte_produto_id,
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
    produto_id = await make_produto_id(repo.dsn, brand="Nvidia", variant="Founders")
    sku = ProductSKU(
        product_url="https://example.com/gpu-to-delete",
        store_name="example",
        search_keyword="rtx 5070",
        produto_id=produto_id,
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
    produto_id = await make_produto_id(repo.dsn, brand="Nvidia", variant="Founders")
    sku = ProductSKU(
        product_url="https://example.com/gpu",
        store_name="example",
        search_keyword="rtx 5070",
        produto_id=produto_id,
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
    async with connect(repo.dsn) as db:
        row = await db.fetchrow(
            "SELECT price_cash, price_installments, installment_count FROM coleta_preco"
        )
        assert row is not None
        assert row["price_cash"] == Decimal("5000.00")
        assert row["price_installments"] == Decimal("5500.00")
        assert row["installment_count"] == 10


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
    produto_id = await make_produto_id(repo.dsn, brand="Nvidia", variant="Founders")
    other_produto_id = await make_produto_id(
        repo.dsn, brand="Nvidia", chipset="rtx 5080", variant="Founders"
    )
    await repo.save_skus(
        [
            ProductSKU(
                product_url="https://example.com/gpu",
                store_name="example",
                search_keyword="rtx 5070",
                produto_id=produto_id,
                brand="Nvidia",
                model="Founders",
                product_title="RTX 5070",
            ),
            ProductSKU(
                product_url="https://example.com/other",
                store_name="example",
                search_keyword="rtx 5080",
                produto_id=other_produto_id,
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
