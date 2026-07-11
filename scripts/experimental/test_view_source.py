import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        print("Navigating to view-source...")
        await page.goto("view-source:https://www.terabyteshop.com.br/produto/37277/placa-de-video-msi-nvidia-geforce-rtx-5070-ti-gaming-trio-oc-white-16gb-gddr7-dlss-ray-tracing", wait_until="domcontentloaded")
        content = await page.content()
        
        # Save to file to examine
        with open("data/view_source_output.html", "w", encoding="utf-8") as f:
            f.write(content)
            
        print("Done. Saved to data/view_source_output.html")
        await browser.close()

asyncio.run(run())
