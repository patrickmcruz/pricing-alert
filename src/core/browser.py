import asyncio
import logging
import random
from typing import Any
from playwright.async_api import async_playwright, Page
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
            # No user_agent override: the installed Chromium (currently v149) already
            # reports its own authentic UA. A hand-maintained UA string drifts out of
            # sync with the real binary (this one was still claiming Chrome/122) and a
            # UA version that doesn't match the browser's actual JS engine / Sec-CH-UA
            # client hints is a textbook bot-detection signal - letting Playwright pass
            # through the real identity keeps every signal mutually consistent.
            viewport={
                "width": random.randint(1880, 1920),
                "height": random.randint(1000, 1080),
            },
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
