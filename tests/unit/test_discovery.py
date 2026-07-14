import json

import pytest
from unittest.mock import AsyncMock

from src.engine.discovery import DiscoveryEngine
from src.repositories.base_repository import PriceRepository


@pytest.fixture
def mock_repository():
    repo = AsyncMock(spec=PriceRepository)
    return repo


@pytest.mark.asyncio
async def test_discovery_engine_run_saves_skus_from_static_manifest(mock_repository, tmp_path):
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

    engine = DiscoveryEngine(mock_repository, target_urls_path=str(manifest))

    await engine.run_discovery(configs=[])

    mock_repository.save_skus.assert_called_once()
    saved_skus = mock_repository.save_skus.call_args[0][0]
    assert len(saved_skus) == 1
    assert saved_skus[0].store_name == "kabum"
    assert saved_skus[0].search_keyword == "rtx 5070"


@pytest.mark.asyncio
async def test_discovery_engine_run_skips_when_manifest_missing(mock_repository, tmp_path):
    missing_path = tmp_path / "does_not_exist.json"

    engine = DiscoveryEngine(mock_repository, target_urls_path=str(missing_path))

    await engine.run_discovery(configs=[])

    mock_repository.save_skus.assert_not_called()
