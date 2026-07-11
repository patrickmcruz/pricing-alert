import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        page = await browser.new_page()
        await page.goto('view-source:https://www.mercadolivre.com.br/placa-de-video-pny-nvidia-geforce-rtx-5070-oc-12gb-gddr7-dlss-ray-tracing-vcg507012tfxpb1-o/p/MLB53508354', wait_until='domcontentloaded')
        raw_html = await page.evaluate("() => Array.from(document.querySelectorAll('.line-content')).map(e => e.textContent).join('\\n')")
        
        print('Length:', len(raw_html))
        print(raw_html[:300])
        print('---')
        print(raw_html[-300:])
            
        await browser.close()

asyncio.run(run())
