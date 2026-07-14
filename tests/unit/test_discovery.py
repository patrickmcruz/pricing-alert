import json

import pytest
from unittest.mock import AsyncMock

from src.core.catalog import Brand, ChipMaker, GpuChipset, GpuModel
from src.engine.discovery import DiscoveryEngine
from src.repositories.base_repository import PriceRepository
from src.repositories.catalog_repository import CatalogRepository


@pytest.fixture
def mock_repository():
    repo = AsyncMock(spec=PriceRepository)
    repo.list_target_urls_missing_gpu_model.return_value = []
    return repo


@pytest.fixture
def mock_catalog_repository():
    catalog = AsyncMock(spec=CatalogRepository)
    catalog.get_or_create_chipset.return_value = GpuChipset(
        id="chipset-1", name="rtx 5070", chip_maker=ChipMaker.NVIDIA
    )
    catalog.get_or_create_brand.return_value = Brand(id="brand-1", name="MockBrand")
    catalog.get_or_create_gpu_model.return_value = GpuModel(
        id="gpu-model-1", brand_id="brand-1", chipset_id="chipset-1", model_name="MockModel"
    )
    return catalog


@pytest.mark.asyncio
async def test_discovery_engine_run_saves_skus_from_static_manifest(
    mock_repository, mock_catalog_repository, tmp_path
):
    manifest = tmp_path / "target_urls.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "store_name": "kabum",
                    "search_keyword": "rtx 5070",
                    "product_url": "https://www.kabum.com.br/produto/123",
                    "brand": "MockBrand",
                    "model": "MockModel",
                    "product_title": "Mock Product",
                }
            ]
        ),
        encoding="utf-8",
    )

    engine = DiscoveryEngine(mock_repository, mock_catalog_repository, target_urls_path=str(manifest))

    await engine.run_discovery(configs=[])

    mock_repository.save_skus.assert_called_once()
    saved_skus = mock_repository.save_skus.call_args[0][0]
    assert len(saved_skus) == 1
    assert saved_skus[0].store_name == "kabum"
    assert saved_skus[0].search_keyword == "rtx 5070"
    assert saved_skus[0].gpu_model_id == "gpu-model-1"


@pytest.mark.asyncio
async def test_discovery_engine_run_skips_when_manifest_missing(
    mock_repository, mock_catalog_repository, tmp_path
):
    missing_path = tmp_path / "does_not_exist.json"

    engine = DiscoveryEngine(mock_repository, mock_catalog_repository, target_urls_path=str(missing_path))

    await engine.run_discovery(configs=[])

    mock_repository.save_skus.assert_not_called()


@pytest.mark.asyncio
async def test_discovery_engine_backfills_legacy_rows_missing_gpu_model(
    mock_repository, mock_catalog_repository, tmp_path
):
    from src.core.contract import LegacyTargetUrlRow

    missing_path = tmp_path / "does_not_exist.json"
    mock_repository.list_target_urls_missing_gpu_model.return_value = [
        LegacyTargetUrlRow(
            product_url="https://example.com/legacy",
            store_name="kabum",
            search_keyword="rtx 5070",
            brand="MockBrand",
            model="MockModel",
            product_title="Legacy Product",
        )
    ]

    engine = DiscoveryEngine(mock_repository, mock_catalog_repository, target_urls_path=str(missing_path))

    await engine.run_discovery(configs=[])

    mock_repository.set_sku_gpu_model_id.assert_called_once_with(
        "https://example.com/legacy", "gpu-model-1"
    )
