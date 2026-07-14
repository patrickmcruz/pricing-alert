import asyncio
import random
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def apply_jitter(min_seconds: float = 3.0, max_seconds: float = 8.0) -> None:
    """Applies a randomized asynchronous delay to reduce deterministic request patterns."""
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


async def _move_mouse_naturally(page: Page, waypoints: int = 4) -> None:
    """
    Moves the mouse through several waypoints with varied step counts, instead of
    teleporting between random points - a closer approximation of a human dragging
    a cursor across the screen than uniform, identically-paced jumps.
    """
    for _ in range(waypoints):
        x = random.randint(80, 1800)
        y = random.randint(80, 900)
        await page.mouse.move(x, y, steps=random.randint(8, 25))
        await asyncio.sleep(random.uniform(0.08, 0.4))


async def _scroll_naturally(page: Page) -> None:
    """Scrolls in a few uneven increments, with an occasional small back-scroll,
    rather than one fixed down/down/up sequence repeated identically every time."""
    for _ in range(random.randint(2, 4)):
        amount = random.randint(150, 600)
        await page.evaluate(f"window.scrollBy(0, {amount})")
        await asyncio.sleep(random.uniform(0.4, 1.3))
    if random.random() < 0.5:
        await page.evaluate(f"window.scrollBy(0, {-random.randint(100, 350)})")
        await asyncio.sleep(random.uniform(0.3, 0.9))


async def _hover_random_element(page: Page) -> None:
    """Occasionally hovers a real link/image on the page, generating the mouseover/
    mousemove events a passive visitor produces just by browsing, not interacting."""
    try:
        if random.random() >= 0.6:
            return
        handle = await page.query_selector("a, img")
        if not handle:
            return
        box = await handle.bounding_box()
        if not box:
            return
        await page.mouse.move(
            box["x"] + box["width"] / 2,
            box["y"] + box["height"] / 2,
            steps=random.randint(8, 20),
        )
        await asyncio.sleep(random.uniform(0.2, 0.6))
    except Exception:
        pass


async def simulate_human_interaction(page: Page, max_attempts: int = 3) -> bool:
    """
    Simulates human behavior to bypass anti-bot protections like Cloudflare.
    Returns True if the page successfully cleared the protection.
    """
    for attempt in range(max_attempts):
        logger.debug("Simulating human behavior (attempt %d)...", attempt + 1)

        # A real visitor pauses to look at the page before doing anything at all.
        await asyncio.sleep(random.uniform(0.8, 2.2))

        await _move_mouse_naturally(page)
        await _scroll_naturally(page)
        await _hover_random_element(page)

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

        await asyncio.sleep(random.uniform(2.5, 4.0))

    return False
