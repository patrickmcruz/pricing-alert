import asyncio
from playwright.async_api import async_playwright

async def fetch_ml():
    async with async_playwright() as p:
        # Launch Chromium headless
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        # In a real scenario we'd use playwright-stealth here. Let's try standard first with custom UA
        page = await context.new_page()
        
        # Apply stealth (if installed)
        try:
            from playwright_stealth import stealth_async
            await stealth_async(page)
            print("Playwright stealth applied.")
        except ImportError:
            print("playwright_stealth not found, proceeding without it.")

        url = "https://www.mercadolivre.com.br/placa-de-video-pny-nvidia-geforce-rtx-5070-oc-12gb-gddr7-dlss-ray-tracing-vcg507012tfxpb1-o/p/MLB53508354"
        print(f"Navigating to {url}")
        
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # Wait for the price block to load to ensure it's not a captcha
        try:
            await page.wait_for_selector(".ui-pdp-price__second-line", timeout=10000)
            print("Found main price block.")
        except Exception as e:
            print("Could not find price block. Might be captcha or different layout:", e)
            
        html = await page.content()
        
        with open("data/mercadolivre.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("HTML saved to data/mercadolivre.html")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(fetch_ml())
