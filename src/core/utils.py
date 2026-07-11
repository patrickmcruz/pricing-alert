import asyncio
import random
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)

async def simulate_human_interaction(page: Page, max_attempts: int = 3):
    """
    Simulates human behavior to bypass anti-bot protections like Cloudflare.
    Returns True if the page successfully cleared the protection.
    """
    for attempt in range(max_attempts):
        logger.debug("Simulating human behavior (attempt %d)...", attempt + 1)
        
        # Randomly move the mouse
        for _ in range(5):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await page.mouse.move(x, y, steps=10)
            await asyncio.sleep(random.uniform(0.1, 0.5))
        
        # Scroll down and up
        await page.evaluate("window.scrollBy(0, 500)")
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await page.evaluate("window.scrollBy(0, 300)")
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await page.evaluate("window.scrollBy(0, -400)")
        
        # Try interacting with Cloudflare iframes if present
        try:
            cf_iframe = await page.query_selector("iframe[src*='cloudflare']")
            if cf_iframe:
                box = await cf_iframe.bounding_box()
                if box:
                    await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=10)
                    await asyncio.sleep(1)
                    await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        except Exception:
            pass

        title = await page.title()
        if "Just a moment" not in title:
            logger.debug("Successfully bypassed protection. Title: %s", title)
            return True
        
        await asyncio.sleep(3)
        
    return False
