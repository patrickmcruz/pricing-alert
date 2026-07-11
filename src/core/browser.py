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
        self._lock = asyncio.Lock()

    async def _init_browser(self):
        async with self._lock:
            if not self.browser:
                if not self.playwright:
                    self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(
                    headless=settings.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-infobars",
                        "--start-maximized"
                    ]
                )

    async def create(self, scraper: Any) -> Page:
        await self._init_browser()
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            permissions=["geolocation"],
        )
        
        # Inject standard webdriver evasion
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = {
                runtime: {}
            };
        """)

        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        return page

    async def close(self, page: Page) -> None:
        try:
            await page.close()
        except Exception:
            pass
