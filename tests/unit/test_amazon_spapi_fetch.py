import httpx
import pytest
import respx

from src.core.config import settings
from src.core.contract import ProductSKU
from src.scrapers.amazon_spapi import AmazonSPAPIScraper

TOKEN_URL = "https://api.amazon.com/auth/o2/token"
PRICING_URL = "https://sellingpartnerapi-na.amazon.com/products/pricing/v0/items/B0DXXXXXXX/offers"


@pytest.fixture
def scraper():
    return AmazonSPAPIScraper()


@pytest.fixture
def sku():
    return ProductSKU(
        product_url="https://www.amazon.com.br/dp/B0DXXXXXXX",
        store_name="amazon",
        search_keyword="rtx 5070",
        gpu_model_id="test-gpu-model-id",
        product_title="Placa de vídeo",
    )


@pytest.fixture(autouse=True)
def amazon_credentials(monkeypatch):
    monkeypatch.setattr(settings, "amazon_lwa_client_id", "test-client-id")
    monkeypatch.setattr(settings, "amazon_lwa_client_secret", "test-client-secret")
    monkeypatch.setattr(settings, "amazon_sp_api_refresh_token", "test-refresh-token")
    monkeypatch.setattr(settings, "amazon_spapi_base_url", "https://sellingpartnerapi-na.amazon.com")
    monkeypatch.setattr(settings, "amazon_marketplace_id", "A2Q3Y263D00KWC")
    monkeypatch.setattr(settings, "amazon_spapi_sandbox", False)


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_success(scraper):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 3600})
    )

    async with httpx.AsyncClient() as client:
        token = await scraper._get_access_token(client)

    assert token == "tok123"
    assert scraper._access_token == "tok123"


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_is_cached_across_calls(scraper):
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 3600})
    )

    async with httpx.AsyncClient() as client:
        first = await scraper._get_access_token(client)
        second = await scraper._get_access_token(client)

    assert first == second == "tok123"
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_get_access_token_returns_none_without_lwa_credentials(scraper, monkeypatch):
    monkeypatch.setattr(settings, "amazon_lwa_client_id", None)
    monkeypatch.setattr(settings, "amazon_lwa_client_secret", None)

    async with httpx.AsyncClient() as client:
        token = await scraper._get_access_token(client)

    assert token is None


@pytest.mark.asyncio
async def test_get_access_token_returns_none_without_refresh_token(scraper, monkeypatch):
    monkeypatch.setattr(settings, "amazon_sp_api_refresh_token", None)

    async with httpx.AsyncClient() as client:
        token = await scraper._get_access_token(client)

    assert token is None


@pytest.mark.asyncio
@respx.mock
async def test_get_access_token_returns_none_on_auth_failure(scraper):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, text="unauthorized"))

    async with httpx.AsyncClient() as client:
        token = await scraper._get_access_token(client)

    assert token is None


@pytest.mark.parametrize(
    "url,expected_asin",
    [
        ("https://www.amazon.com.br/Placa-Video/dp/B0DXXXXXXX", "B0DXXXXXXX"),
        ("https://www.amazon.com.br/gp/product/B0DXXXXXXX", "B0DXXXXXXX"),
        ("https://www.amazon.com.br/dp/b0dxxxxxxx?ref=abc", "B0DXXXXXXX"),
    ],
)
def test_extract_asin_from_url(scraper, url, expected_asin):
    assert scraper._extract_asin_from_url(url) == expected_asin


def test_extract_asin_from_url_returns_none_when_missing(scraper):
    assert scraper._extract_asin_from_url("https://www.amazon.com.br/s?k=rtx+5070") is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_offers_document(scraper, sku):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 3600})
    )
    respx.get(PRICING_URL).mock(
        return_value=httpx.Response(
            200,
            json={"payload": {"Offers": [{"ListingPrice": {"Amount": 4500.0, "CurrencyCode": "BRL"}}]}},
        )
    )

    async with httpx.AsyncClient() as client:
        document = await scraper.fetch(sku, client)

    assert "Offers" in document


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_empty_string_when_auth_fails(scraper, sku):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, text="unauthorized"))

    async with httpx.AsyncClient() as client:
        document = await scraper.fetch(sku, client)

    assert document == ""


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_empty_string_when_pricing_api_fails(scraper, sku):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 3600})
    )
    respx.get(PRICING_URL).mock(return_value=httpx.Response(500, text="server error"))

    async with httpx.AsyncClient() as client:
        document = await scraper.fetch(sku, client)

    assert document == ""


@pytest.mark.asyncio
async def test_fetch_returns_empty_string_when_asin_cannot_be_extracted(scraper):
    bad_sku = ProductSKU(
        product_url="https://www.amazon.com.br/s?k=rtx+5070",
        store_name="amazon",
        search_keyword="rtx 5070",
        gpu_model_id="test-gpu-model-id",
        product_title="Placa de vídeo",
    )

    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.post(TOKEN_URL).mock(
                return_value=httpx.Response(200, json={"access_token": "tok123", "expires_in": 3600})
            )
            document = await scraper.fetch(bad_sku, client)

    assert document == ""
