import asyncio
import logging
from src.core.config import settings
from src.core.catalog import GPU_CATEGORY_SLUG, ChipMaker, infer_chip_maker
from src.db.schema import initialize_schema as initialize_db_schema
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository
from src.repositories.postgres_repository import PostgresPriceRepository
from src.scrapers.mercadolivre import MercadoLivreScraper

logging.basicConfig(level=logging.INFO)

from src.core.contract import ProductSKU

async def main():
    await initialize_db_schema(settings.db_dsn)
    repo = PostgresPriceRepository(settings.db_dsn)
    catalog = PostgresCatalogRepository(settings.db_dsn)

    # 1. Seed SKUs (resolving marca/categoria/produto through the catalog first)
    categoria = await catalog.get_or_create_categoria("GPU", GPU_CATEGORY_SLUG)
    pny = await catalog.get_or_create_marca("PNY")
    zotac = await catalog.get_or_create_marca("Zotac")
    pny_produto = await catalog.get_or_create_produto(
        pny.id, categoria.id, "rtx 5070",
        specs={"chipset": "rtx 5070", "chip_maker": ChipMaker.NVIDIA.value},
    )
    zotac_produto = await catalog.get_or_create_produto(
        zotac.id, categoria.id, "rtx 5070 ti",
        specs={"chipset": "rtx 5070 ti", "chip_maker": ChipMaker.NVIDIA.value},
    )

    skus_to_seed = [
        ProductSKU(
            product_url="https://www.mercadolivre.com.br/placa-de-video-pny-nvidia-geforce-rtx-5070-oc-12gb-gddr7-dlss-ray-tracing-vcg507012tfxpb1-o/p/MLB53508354",
            store_name="mercado-livre",
            search_keyword="rtx 5070",
            produto_id=pny_produto.id,
            brand=pny.nome,
            model=pny_produto.nome,
            product_title="Placa De Vídeo Pny Nvidia Geforce Rtx 5070 Oc"
        ),
        ProductSKU(
            product_url="https://www.mercadolivre.com.br/placa-de-video-zotac-rtx-5070ti-gaming-solid-sff-oc-16gb/p/MLB53264127",
            store_name="mercado-livre",
            search_keyword="rtx 5070 ti",
            produto_id=zotac_produto.id,
            brand=zotac.nome,
            model=zotac_produto.nome,
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
