from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.core.config import settings
from src.core.http_client import HTTPClientFactory


@pytest.mark.asyncio
async def test_create_configures_http2_redirects_and_timeout(monkeypatch):
    captured_kwargs = {}

    def fake_async_client(**kwargs):
        captured_kwargs.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)

    factory = HTTPClientFactory()
    await factory.create(scraper=None)

    assert captured_kwargs["http2"] is True
    assert captured_kwargs["follow_redirects"] is True
    assert captured_kwargs["timeout"] == settings.http_timeout_seconds


@pytest.mark.asyncio
async def test_create_sets_browser_like_headers(monkeypatch):
    captured_kwargs = {}

    def fake_async_client(**kwargs):
        captured_kwargs.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)

    await HTTPClientFactory().create(scraper=None)

    headers = captured_kwargs["headers"]
    assert "Mozilla" in headers["User-Agent"]
    assert "text/html" in headers["Accept"]
    assert "pt-BR" in headers["Accept-Language"]


@pytest.mark.asyncio
async def test_create_returns_the_constructed_client(monkeypatch):
    sentinel_client = MagicMock()
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: sentinel_client)

    result = await HTTPClientFactory().create(scraper=None)

    assert result is sentinel_client


@pytest.mark.asyncio
async def test_close_calls_aclose_on_the_client():
    client = AsyncMock()

    await HTTPClientFactory().close(client)

    client.aclose.assert_awaited_once()
