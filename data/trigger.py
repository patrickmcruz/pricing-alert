import asyncio
import logging
from src.core.config import settings
from src.repositories.sqlite_repository import SQLitePriceRepository
from src.scrapers.mercadolivre import MercadoLivreScraper

logging.basicConfig(level=logging.INFO)

async def main():
    repo = SQLitePriceRepository(settings.db_path)
    await repo.initialize_schema()
    
    scraper = MercadoLivreScraper()
    skus = await repo.get_target_skus("mercado-livre")
    
    print(f"Found {len(skus)} target URLs for ML")
    prices = []
    for sku in skus:
        print(f"Scraping {sku.product_url}")
        price = await scraper.execute(sku, None)
        if price:
            print(f"Saved: {price.price_cash} (Avail: {price.is_available})")
            prices.append(price)
        else:
            print("No price returned.")
            
    if prices:
        await repo.save_prices(prices)
        print(f"Saved {len(prices)} to DB.")

if __name__ == "__main__":
    asyncio.run(main())
