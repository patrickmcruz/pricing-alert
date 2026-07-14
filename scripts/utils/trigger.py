import asyncio
import logging
from src.core.config import settings
from src.core.catalog import ChipMaker
from src.repositories.sqlite_catalog_repository import SQLiteCatalogRepository
from src.repositories.sqlite_repository import SQLitePriceRepository
from src.scrapers.mercadolivre import MercadoLivreScraper

logging.basicConfig(level=logging.INFO)

from src.core.contract import ProductSKU

async def main():
    repo = SQLitePriceRepository(settings.db_path)
    await repo.initialize_schema()
    catalog = SQLiteCatalogRepository(settings.db_path)
    await catalog.initialize_schema()

    # 1. Seed SKUs (resolving brand/chipset/model through the catalog first)
    rtx_5070 = await catalog.get_or_create_chipset("rtx 5070", chip_maker=ChipMaker.NVIDIA)
    rtx_5070_ti = await catalog.get_or_create_chipset("rtx 5070 ti", chip_maker=ChipMaker.NVIDIA)
    pny = await catalog.get_or_create_brand("PNY")
    zotac = await catalog.get_or_create_brand("Zotac")
    pny_model = await catalog.get_or_create_gpu_model(pny.id, rtx_5070.id, "rtx 5070")
    zotac_model = await catalog.get_or_create_gpu_model(zotac.id, rtx_5070_ti.id, "rtx 5070 ti")

    skus_to_seed = [
        ProductSKU(
            product_url="https://www.mercadolivre.com.br/placa-de-video-pny-nvidia-geforce-rtx-5070-oc-12gb-gddr7-dlss-ray-tracing-vcg507012tfxpb1-o/p/MLB53508354",
            store_name="mercado-livre",
            search_keyword=rtx_5070.name,
            gpu_model_id=pny_model.id,
            brand=pny.name,
            model=pny_model.variant_name,
            product_title="Placa De Vídeo Pny Nvidia Geforce Rtx 5070 Oc"
        ),
        ProductSKU(
            product_url="https://www.mercadolivre.com.br/placa-de-video-zotac-rtx-5070ti-gaming-solid-sff-oc-16gb/p/MLB53264127",
            store_name="mercado-livre",
            search_keyword=rtx_5070_ti.name,
            gpu_model_id=zotac_model.id,
            brand=zotac.name,
            model=zotac_model.variant_name,
            product_title="Placa De Vídeo Zotac Rtx 5070ti Gaming Solid Sff Oc"
        )
    ]
    await repo.save_skus(skus_to_seed)
    
    # 2. Run Scraper
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
