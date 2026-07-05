import asyncio
import os
import sys
import aiosqlite

# Ensure src module is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.repositories.sqlite_repository import SQLitePriceRepository
from src.scrapers.kabum import KabumScraper
from src.scrapers.terabyte import TerabyteScraper

async def seed():
    print("Seeding database with mock data from fixtures...")
    db_path = os.path.join(PROJECT_ROOT, "data", "prices.db")
    
    # Clear the database
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM prices")
        await db.commit()
        
    repo = SQLitePriceRepository(db_path)
    await repo.initialize_schema()
    
    # Seed Kabum Mock Data
    kabum = KabumScraper()
    fixture_path_kabum = os.path.join(PROJECT_ROOT, "tests", "fixtures", "kabum_mock.html")
    with open(fixture_path_kabum, encoding="utf-8") as f:
        html = f.read()
    products_kabum = kabum.parse(html, "rtx 5070") + kabum.parse(html, "rtx 5070 ti")
    await repo.save_prices(products_kabum)
    
    # Seed Terabyte Mock Data
    terabyte = TerabyteScraper()
    fixture_path_terabyte = os.path.join(PROJECT_ROOT, "tests", "fixtures", "terabyte_mock.html")
    with open(fixture_path_terabyte, encoding="utf-8") as f:
        html = f.read()
    products_terabyte = terabyte.parse(html, "rtx 5070") + terabyte.parse(html, "rtx 5070 ti")
    await repo.save_prices(products_terabyte)
    
    print(f"Successfully inserted {len(products_kabum) + len(products_terabyte)} records into prices.db!")

if __name__ == "__main__":
    asyncio.run(seed())
