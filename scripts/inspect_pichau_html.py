import asyncio
import re

from playwright.async_api import async_playwright

urls = [
    'https://www.pichau.com.br/placa-de-video-msi-geforce-rtx-5070-12gb',
    'https://www.pichau.com.br/placa-de-video-msi-geforce-rtx-5070-ti-16gb',
]


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        for url in urls:
            print('URL', url)
            await page.goto(url, wait_until='networkidle', timeout=60000)
            html = await page.content()
            print('has __next_f', '__next_f' in html)
            print('has __NEXT_DATA__', '__NEXT_DATA__' in html)
            print('has pichau_prices', 'pichau_prices' in html)
            print('has stock_status', 'stock_status' in html)
            print('script tags', html.count('<script'))
            m = re.search(r'self\.__next_f\.push\(', html)
            print('push found', bool(m))
            if m:
                start = max(0, m.start() - 300)
                end = min(len(html), m.end() + 1500)
                print(html[start:end])
            print('---')
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
