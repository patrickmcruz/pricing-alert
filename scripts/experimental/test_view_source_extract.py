import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        page = await browser.new_page()
        await page.goto("view-source:https://www.terabyteshop.com.br/produto/37277/placa-de-video-msi-nvidia-geforce-rtx-5070-ti-gaming-trio-oc-white-16gb-gddr7-dlss-ray-tracing", wait_until="domcontentloaded")
        raw_html = await page.evaluate("() => Array.from(document.querySelectorAll('.line-content')).map(e => e.textContent).join('\\n')")
        
        soup = BeautifulSoup(raw_html, 'lxml')
        elem = soup.find(id='valVista')
        if elem:
            print('SUCCESS: Found valVista tag! Value:', elem.text.strip())
        else:
            print('FAILED: Still no tag.')
            
        await browser.close()

asyncio.run(run())
