import json

import httpx
import pytest
import respx

from src.core.config import settings
from src.core.contract import ProductSKU
from src.scrapers.mercadolivre import MercadoLivreScraper


@pytest.fixture
def scraper():
    return MercadoLivreScraper()


@pytest.fixture
def catalog_sku():
    return ProductSKU(
        product_url="https://produto.mercadolivre.com.br/p/MLB53508354",
        store_name="mercado-livre",
        search_keyword="rtx 5070",
        gpu_model_id="test-gpu-model-id",
        product_title="Placa de vídeo",
    )


@pytest.fixture
def item_sku():
    return ProductSKU(
        product_url="https://produto.mercadolivre.com.br/MLB-53508354-placa",
        store_name="mercado-livre",
        search_keyword="rtx 5070",
        gpu_model_id="test-gpu-model-id",
        product_title="Placa de vídeo",
    )


@pytest.fixture(autouse=True)
def ml_credentials(monkeypatch):
    monkeypatch.setattr(settings, "ml_app_id", "test-app-id")
    monkeypatch.setattr(settings, "ml_secret_key", "test-secret")


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_success(scraper):
    respx.post("https://api.mercadolibre.com/oauth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 21600})
    )

    async with httpx.AsyncClient() as client:
        token = await scraper._get_access_token(client)

    assert token == "tok123"
    assert scraper._access_token == "tok123"


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_is_cached_across_calls(scraper):
    route = respx.post("https://api.mercadolibre.com/oauth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 21600})
    )

    async with httpx.AsyncClient() as client:
        first = await scraper._get_access_token(client)
        second = await scraper._get_access_token(client)

    assert first == second == "tok123"
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_get_access_token_returns_none_without_credentials(scraper, monkeypatch):
    monkeypatch.setattr(settings, "ml_app_id", None)
    monkeypatch.setattr(settings, "ml_secret_key", None)

    async with httpx.AsyncClient() as client:
        token = await scraper._get_access_token(client)

    assert token is None


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_returns_none_on_auth_failure(scraper):
    respx.post("https://api.mercadolibre.com/oauth/token").mock(
        return_value=httpx.Response(401, text="unauthorized")
    )

    async with httpx.AsyncClient() as client:
        token = await scraper._get_access_token(client)

    assert token is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_catalog_product_combines_product_and_items(scraper, catalog_sku):
    respx.post("https://api.mercadolibre.com/oauth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 21600})
    )
    respx.get("https://api.mercadolibre.com/products/MLB53508354").mock(
        return_value=httpx.Response(200, json={"name": "Placa de vídeo"})
    )
    respx.get("https://api.mercadolibre.com/products/MLB53508354/items").mock(
        return_value=httpx.Response(200, json={"results": [{"price": 4500.0, "listing_type_id": "gold_pro"}]})
    )

    async with httpx.AsyncClient() as client:
        document = await scraper.fetch(catalog_sku, client)

    data = json.loads(document)
    assert data["type"] == "catalog"
    assert data["product"]["name"] == "Placa de vídeo"
    assert len(data["items"]) == 1


@pytest.mark.asyncio
@respx.mock
async def test_fetch_item_listing(scraper, item_sku):
    respx.post("https://api.mercadolibre.com/oauth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 21600})
    )
    respx.get("https://api.mercadolibre.com/items/MLB53508354").mock(
        return_value=httpx.Response(
            200,
            json={"title": "Placa de vídeo", "status": "active", "available_quantity": 3, "price": 4500.0},
        )
    )

    async with httpx.AsyncClient() as client:
        document = await scraper.fetch(item_sku, client)

    data = json.loads(document)
    assert data["type"] == "item"
    assert data["item"]["price"] == 4500.0


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_empty_string_when_auth_fails(scraper, catalog_sku):
    respx.post("https://api.mercadolibre.com/oauth/token").mock(
        return_value=httpx.Response(401, text="unauthorized")
    )

    async with httpx.AsyncClient() as client:
        document = await scraper.fetch(catalog_sku, client)

    assert document == ""


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_empty_string_when_product_api_fails(scraper, catalog_sku):
    respx.post("https://api.mercadolibre.com/oauth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 21600})
    )
    respx.get("https://api.mercadolibre.com/products/MLB53508354").mock(
        return_value=httpx.Response(500, text="server error")
    )

    async with httpx.AsyncClient() as client:
        document = await scraper.fetch(catalog_sku, client)

    assert document == ""
