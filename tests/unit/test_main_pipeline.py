import pytest

import main
from src.core.store import Store


class FakeStoreRepository:
    def __init__(self, stores):
        self._stores = stores

    async def list_stores(self):
        return self._stores


@pytest.mark.asyncio
async def test_load_stores_config_uses_database_store_rows(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_registered_scrapers",
        lambda: {"pichau": object(), "kabum": object()},
    )

    repo = FakeStoreRepository([
        Store(slug="pichau", display_name="Pichau", is_active=True),
        Store(slug="kabum", display_name="Kabum", is_active=True),
        Store(slug="amazon", display_name="Amazon", is_active=False),
    ])

    configs = await main.load_stores_config(repo)

    assert [config.store_name for config in configs] == ["pichau", "kabum"]
    assert configs[0].enabled is True
    assert configs[1].enabled is True
