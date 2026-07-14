import asyncio
import os
import sys

# Ensure src module is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.scrappers.kabum import KabumScraper
from src.core.browser import BrowserFactory
from src.core.contract import ProductSKU

async def test():
    scraper = KabumScraper()
    factory = BrowserFactory()
    
    sku = ProductSKU(
        store_name="kabum",
        search_keyword="rtx 5070",
        brand="MSI",
        model="Shadow 2X OC",
        product_title="Placa De Video Msi Rtx 5070 12gb Gddr7",
        product_url="https://www.kabum.com.br/produto/875474/placa-de-video-msi-rtx-5070-12gb-gddr7-192-bits-shadow-2x-oc-912-v532-011"
    )
    
    print(f"Initializing HTTP Client and fetching {sku.product_url}...")
    client = await factory.create(scraper)
    
    try:
        price = await scraper.execute(sku, client)
        if price:
            print("\n✅ SCRAPE SUCCESSFUL!")
            print(f"Product: {price.product_title}")
            print(f"Cash Price: R$ {price.price_cash}")
            print(f"Installments: R$ {price.price_installments}")
            print(f"Available: {price.is_available}")
            print(f"Discount: R$ {price.discount}")
            print(f"Parser Version: {price.parser_version}")
        else:
            print("\n❌ SCRAPE FAILED or returned None.")
    finally:
        await factory.close(client)

if __name__ == "__main__":
    asyncio.run(test())
