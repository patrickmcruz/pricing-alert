import asyncio
import logging
from typing import Any
from playwright.async_api import async_playwright, BrowserContext, Page
from playwright_stealth import Stealth
from src.core.config import settings

logger = logging.getLogger(__name__)

class BrowserFactory:
    """Factory for managing Playwright browser contexts."""

    def __init__(self):
        self.playwright = None
        self.browser = None

    async def _init_browser(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=settings.headless)

    async def create(self, scraper: Any) -> Page:
        await self._init_browser()
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
        )
        page = await context.new_page()
        # Apply stealth to bypass basic anti-bot detections
        await Stealth().apply_stealth_async(page)
        return page

    async def close(self, page: Page) -> None:
        try:
            await page.close()
        except Exception:
            pass
