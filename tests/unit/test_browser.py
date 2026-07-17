from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core import browser as browser_module
from src.core.browser import BrowserFactory
from src.core.config import settings


def _mock_playwright_chain():
    """Builds the chromium.launch(...).new_context(...).new_page(...) mock chain
    async_playwright().start() would normally produce, so _init_browser()/create()
    never touch a real browser."""
    page = AsyncMock()
    page.set_default_timeout = MagicMock()  # real Playwright's Page.set_default_timeout is sync
    context = AsyncMock()
    context.new_page.return_value = page
    browser = AsyncMock()
    browser.new_context.return_value = context
    playwright_obj = MagicMock()
    playwright_obj.chromium.launch = AsyncMock(return_value=browser)

    async_playwright_result = MagicMock()
    async_playwright_result.start = AsyncMock(return_value=playwright_obj)

    return async_playwright_result, playwright_obj, browser, context, page


@pytest.fixture(autouse=True)
def stub_stealth(monkeypatch):
    stealth_instance = MagicMock()
    stealth_instance.apply_stealth_async = AsyncMock()
    monkeypatch.setattr(browser_module, "Stealth", MagicMock(return_value=stealth_instance))
    return stealth_instance


@pytest.mark.asyncio
async def test_init_browser_launches_chromium_with_configured_headless(monkeypatch):
    async_playwright_result, playwright_obj, browser, _, _ = _mock_playwright_chain()
    monkeypatch.setattr(browser_module, "async_playwright", lambda: async_playwright_result)
    monkeypatch.setattr(settings, "headless", True)

    factory = BrowserFactory()
    await factory._init_browser()

    playwright_obj.chromium.launch.assert_awaited_once()
    _, kwargs = playwright_obj.chromium.launch.call_args
    assert kwargs["headless"] is True
    assert "--no-sandbox" in kwargs["args"]
    assert factory.browser is browser


@pytest.mark.asyncio
async def test_init_browser_only_launches_once(monkeypatch):
    async_playwright_result, playwright_obj, _, _, _ = _mock_playwright_chain()
    monkeypatch.setattr(browser_module, "async_playwright", lambda: async_playwright_result)

    factory = BrowserFactory()
    await factory._init_browser()
    await factory._init_browser()

    async_playwright_result.start.assert_awaited_once()
    playwright_obj.chromium.launch.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_builds_context_with_expected_options(monkeypatch):
    async_playwright_result, _, _, _, _ = _mock_playwright_chain()
    monkeypatch.setattr(browser_module, "async_playwright", lambda: async_playwright_result)
    monkeypatch.setattr(settings, "display_timezone", "America/Sao_Paulo")

    factory = BrowserFactory()
    await factory.create(scraper=None)

    _, kwargs = factory.browser.new_context.call_args
    assert kwargs["locale"] == "pt-BR"
    assert kwargs["timezone_id"] == "America/Sao_Paulo"
    assert kwargs["permissions"] == ["geolocation"]
    assert 1880 <= kwargs["viewport"]["width"] <= 1920
    assert 1000 <= kwargs["viewport"]["height"] <= 1080


@pytest.mark.asyncio
async def test_create_injects_webdriver_evasion_script(monkeypatch):
    async_playwright_result, _, _, context, _ = _mock_playwright_chain()
    monkeypatch.setattr(browser_module, "async_playwright", lambda: async_playwright_result)

    await BrowserFactory().create(scraper=None)

    context.add_init_script.assert_awaited_once()
    (script,), _ = context.add_init_script.call_args
    assert "webdriver" in script


@pytest.mark.asyncio
async def test_create_sets_navigation_timeout_on_the_page(monkeypatch):
    async_playwright_result, _, _, _, page = _mock_playwright_chain()
    monkeypatch.setattr(browser_module, "async_playwright", lambda: async_playwright_result)
    monkeypatch.setattr(settings, "navigation_timeout_ms", 12345)

    returned_page = await BrowserFactory().create(scraper=None)

    returned_page.set_default_timeout.assert_called_once_with(12345)
    assert returned_page is page


@pytest.mark.asyncio
async def test_create_applies_stealth_to_the_page(monkeypatch, stub_stealth):
    async_playwright_result, _, _, _, page = _mock_playwright_chain()
    monkeypatch.setattr(browser_module, "async_playwright", lambda: async_playwright_result)

    await BrowserFactory().create(scraper=None)

    stub_stealth.apply_stealth_async.assert_awaited_once_with(page)


@pytest.mark.asyncio
async def test_close_closes_the_page():
    page = AsyncMock()

    await BrowserFactory().close(page)

    page.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_swallows_exceptions():
    page = AsyncMock()
    page.close.side_effect = RuntimeError("already closed")

    await BrowserFactory().close(page)  # must not raise
