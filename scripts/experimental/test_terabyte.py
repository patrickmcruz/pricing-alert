import asyncio
import sys
from src.core.config import settings
from src.repositories.sqlite_repository import SQLitePriceRepository
from src.spiders.terabyte_spider import TerabyteSpider
from src.scrapers.terabyte import TerabyteScraper
from src.core.contract import StoreConfig
from src.core.browser import BrowserFactory
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def test_terabyte():
    repo = SQLitePriceRepository(settings.db_path)
    await repo.initialize_schema()
    factory = BrowserFactory()
    
    spider = TerabyteSpider()
    scraper = TerabyteScraper()
    
    configs = [StoreConfig(store_name='terabyte', target_keywords=['rtx 5070'], cron_times=['12:00'])]
    for config in configs:
        client = await factory.create(spider)
        try:
            for keyword in config.target_keywords:
                logging.info(f"Discovering for {config.store_name} with keyword {keyword}...")
                skus = await spider.discover(keyword, client)
                logging.info(f'Found {len(skus)} SKUs for {config.store_name}')
                await repo.save_skus(skus)
        finally:
            await factory.close(client)
        
    # 2. Scrape
    skus = await repo.get_target_skus('terabyte')
    logging.info(f'Found {len(skus)} target SKUs for terabyte in DB')
    
    prices = []
    scraper_client = await factory.create(scraper)
    try:
        for sku in skus[:3]: # test up to 3 items
            logging.info(f'Scraping {sku.product_url}')
            price = await scraper.execute(sku, scraper_client)
            if price:
                prices.append(price)
                logging.info(f'Price found: {price.price_cash}')
            else:
                logging.info('No price found.')
    finally:
        await factory.close(scraper_client)
    
    if prices:
        await repo.save_prices(prices)
        logging.info(f'Saved {len(prices)} prices to DB')
        
if __name__ == "__main__":
    asyncio.run(test_terabyte())
