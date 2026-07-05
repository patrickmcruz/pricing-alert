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
    from src.core.config import settings
    print(f"Seeding database at {settings.db_path} with mock data from fixtures...")
    db_path = settings.db_path
    
    from src.core.contract import ProductSKU
    
    repo = SQLitePriceRepository(db_path)
    await repo.initialize_schema()
    
    # Seed Target URLs (Spiders)
    skus = [
        ProductSKU(
            store_name="kabum",
            search_keyword="rtx 5070",
            brand="MSI",
            model="Shadow 2X OC",
            product_title="Placa De Video Msi Rtx 5070 12gb Gddr7",
            product_url="https://www.kabum.com.br/produto/875474/placa-de-video-msi-rtx-5070-12gb-gddr7-192-bits-shadow-2x-oc-912-v532-011"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword="rtx 5070",
            brand="MSI",
            model="Ventus 2X OC",
            product_title="Placa De Vídeo Msi Geforce Rtx 5070 12g Ventus 2x Oc",
            product_url="https://www.kabum.com.br/produto/725587/placa-de-video-msi-geforce-rtx-5070-12g-ventus-2x-oc-12-gb-gddr7-28gbps-nvidia-geforce-rtx-5070-g5070-12v2c"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword="rtx 5070 ti",
            brand="MSI",
            model="Shadow 3X OC",
            product_title="Placa De Vídeo Nvidia Geforce Msi Rtx5070ti 16gb",
            product_url="https://www.kabum.com.br/produto/857022/placa-de-video-nvidia-geforce-msi-rtx5070ti-16gb-gddr7-256its-shadow-3x-oc-912-v531-097"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword="rtx 5070 ti",
            brand="Gainward",
            model="Phoenix",
            product_title="Placa De Vídeo Gainward Rtx 5070 Ti Phoenix 16gb",
            product_url="https://www.kabum.com.br/produto/996236/placa-de-video-gainward-rtx-5070-ti-phoenix-16gb-gddr7"
        )
    ]
    
    await repo.save_skus(skus)
    print(f"Successfully seeded {len(skus)} target URLs into prices.db! The Orchestrator will scrape these on its next tick.")

if __name__ == "__main__":
    asyncio.run(seed())
