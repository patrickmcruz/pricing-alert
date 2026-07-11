import asyncio
import random
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page
from playwright_stealth import Stealth

async def simulate_human_behavior(page: Page):
    print("Simulating human behavior...")
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
    
    # Check for Turnstile or Cloudflare iframes and try to hover/click around them
    try:
        cf_iframe = await page.query_selector("iframe[src*='cloudflare']")
        if cf_iframe:
            print("Found Cloudflare iframe, attempting to hover...")
            box = await cf_iframe.bounding_box()
            if box:
                await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=10)
                await asyncio.sleep(1)
                await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    except Exception as e:
        print(f"Iframe interaction failed: {e}")

async def run():
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized"
            ]
        )
        context = await browser.new_context(
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
        
        target_url = "https://www.terabyteshop.com.br/produto/37277/placa-de-video-msi-nvidia-geforce-rtx-5070-ti-gaming-trio-oc-white-16gb-gddr7-dlss-ray-tracing"
        print(f"Navigating to {target_url}")
        
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            print("Page loaded. Starting interaction loop...")
            
            for i in range(3):
                await simulate_human_behavior(page)
                # Wait for title to not be 'Just a moment...'
                title = await page.title()
                if "Just a moment" not in title:
                    print(f"Title changed to: {title}")
                    break
                else:
                    print(f"Still in Cloudflare challenge... (attempt {i+1})")
                    await asyncio.sleep(3)
                    
            content = await page.content()
            soup = BeautifulSoup(content, 'lxml')
            
            title_elem = soup.find("h1", class_="tit-prod")
            val_vista = soup.find(id="valVista")
            
            if title_elem and val_vista:
                print("SUCCESS: Found product details!")
                print(f"Title: {title_elem.text.strip()}")
                print(f"Price: {val_vista.text.strip()}")
            else:
                print("FAILED: Did not find product tags.")
                if "Just a moment" in await page.title():
                    print("Status: Blocked by Cloudflare.")
                else:
                    print(f"Status: Page loaded but tags not found. Title: {await page.title()}")
        except Exception as e:
            print(f"Error during execution: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
