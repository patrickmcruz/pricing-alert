import pytest
from unittest.mock import AsyncMock

from src.core.catalog import Categoria, Marca, Produto
from src.core.contract import TargetUrlEntry
from src.engine.discovery import DiscoveryEngine
from src.repositories.base_repository import PriceRepository
from src.repositories.catalog_repository import CatalogRepository
from src.repositories.target_url_repository import TargetUrlRepository


@pytest.fixture
def mock_repository():
    repo = AsyncMock(spec=PriceRepository)
    repo.list_target_urls_missing_produto.return_value = []
    return repo


@pytest.fixture
def mock_catalog_repository():
    catalog = AsyncMock(spec=CatalogRepository)
    catalog.get_or_create_categoria.return_value = Categoria(id="categoria-1", nome="GPU", slug="gpu")
    catalog.get_or_create_marca.return_value = Marca(id="marca-1", nome="MockBrand")
    catalog.get_or_create_produto.return_value = Produto(
        id="produto-1", marca_id="marca-1", categoria_id="categoria-1", nome="MockModel",
        specs={"chipset": "rtx 5070", "chip_maker": "NVIDIA"},
    )
    return catalog


def _mock_target_url_repository(entries: list[TargetUrlEntry]):
    repo = AsyncMock(spec=TargetUrlRepository)
    repo.list_all.return_value = entries
    return repo


@pytest.mark.asyncio
async def test_discovery_engine_run_saves_skus_from_target_urls(
    mock_repository, mock_catalog_repository
):
    target_url_repository = _mock_target_url_repository([
        TargetUrlEntry(
            store_name="kabum",
            search_keyword="rtx 5070",
            product_url="https://www.kabum.com.br/produto/123",
            brand="MockBrand",
            model="MockModel",
            product_title="Mock Product",
        )
    ])

    engine = DiscoveryEngine(mock_repository, mock_catalog_repository, target_url_repository)

    await engine.run_discovery(configs=[])

    mock_repository.save_skus.assert_called_once()
    saved_skus = mock_repository.save_skus.call_args[0][0]
    assert len(saved_skus) == 1
    assert saved_skus[0].store_name == "kabum"
    assert saved_skus[0].search_keyword == "rtx 5070"
    assert saved_skus[0].produto_id == "produto-1"


@pytest.mark.asyncio
async def test_discovery_engine_run_skips_when_target_urls_empty(
    mock_repository, mock_catalog_repository
):
    target_url_repository = _mock_target_url_repository([])

    engine = DiscoveryEngine(mock_repository, mock_catalog_repository, target_url_repository)

    await engine.run_discovery(configs=[])

    mock_repository.save_skus.assert_not_called()


@pytest.mark.asyncio
async def test_discovery_engine_backfills_legacy_rows_missing_produto(
    mock_repository, mock_catalog_repository
):
    from src.core.contract import LegacyTargetUrlRow

    mock_repository.list_target_urls_missing_produto.return_value = [
        LegacyTargetUrlRow(
            product_url="https://example.com/legacy",
            store_name="kabum",
            search_keyword="rtx 5070",
            brand="MockBrand",
            model="MockModel",
            product_title="Legacy Product",
        )
    ]
    target_url_repository = _mock_target_url_repository([])

    engine = DiscoveryEngine(mock_repository, mock_catalog_repository, target_url_repository)

    await engine.run_discovery(configs=[])

    mock_repository.set_sku_produto_id.assert_called_once_with(
        "https://example.com/legacy", "produto-1"
    )
