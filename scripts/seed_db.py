import asyncio
import os
import sys

# Ensure src module is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.repositories.sqlite_repository import SQLitePriceRepository
from src.repositories.sqlite_catalog_repository import SQLiteCatalogRepository

async def seed():
    from src.core.config import settings
    from src.core.catalog import ChipMaker
    print(f"Seeding database at {settings.db_path} with mock data from fixtures...")
    db_path = settings.db_path

    from src.core.contract import ProductSKU

    repo = SQLitePriceRepository(db_path)
    await repo.initialize_schema()
    catalog = SQLiteCatalogRepository(db_path)
    await catalog.initialize_schema()

    # Resolve brand/chipset/variant through the catalog before seeding SKUs.
    msi = await catalog.get_or_create_brand("MSI")
    gainward = await catalog.get_or_create_brand("Gainward")
    xfx = await catalog.get_or_create_brand("xfx")
    rtx_5070 = await catalog.get_or_create_chipset("rtx 5070", chip_maker=ChipMaker.NVIDIA)
    rtx_5070_ti = await catalog.get_or_create_chipset("rtx 5070 ti", chip_maker=ChipMaker.NVIDIA)
    # "oc" in "rx 9070 oc" is search noise, not part of the chipset - canonical name is "rx 9070".
    rx_9070 = await catalog.get_or_create_chipset("rx 9070", chip_maker=ChipMaker.AMD)
    rx_9070_xt = await catalog.get_or_create_chipset("rx 9070 xt", chip_maker=ChipMaker.AMD)

    msi_shadow_2x = await catalog.get_or_create_gpu_model(msi.id, rtx_5070.id, "Shadow 2X OC")
    msi_ventus_2x = await catalog.get_or_create_gpu_model(msi.id, rtx_5070.id, "Ventus 2X OC")
    msi_shadow_3x = await catalog.get_or_create_gpu_model(msi.id, rtx_5070_ti.id, "Shadow 3X OC")
    gainward_phoenix = await catalog.get_or_create_gpu_model(gainward.id, rtx_5070_ti.id, "Phoenix")
    xfx_swift_9070 = await catalog.get_or_create_gpu_model(xfx.id, rx_9070.id, "swift")
    xfx_swift_9070_xt = await catalog.get_or_create_gpu_model(xfx.id, rx_9070_xt.id, "swift")

    # Seed Target URLs (Spiders)
    skus = [
        ProductSKU(
            store_name="kabum",
            search_keyword=rtx_5070.name,
            gpu_model_id=msi_shadow_2x.id,
            brand=msi.name,
            model=msi_shadow_2x.variant_name,
            product_title="Placa De Video Msi Rtx 5070 12gb Gddr7",
            product_url="https://www.kabum.com.br/produto/875474/placa-de-video-msi-rtx-5070-12gb-gddr7-192-bits-shadow-2x-oc-912-v532-011"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword=rtx_5070.name,
            gpu_model_id=msi_ventus_2x.id,
            brand=msi.name,
            model=msi_ventus_2x.variant_name,
            product_title="Placa De Vídeo Msi Geforce Rtx 5070 12g Ventus 2x Oc",
            product_url="https://www.kabum.com.br/produto/725587/placa-de-video-msi-geforce-rtx-5070-12g-ventus-2x-oc-12-gb-gddr7-28gbps-nvidia-geforce-rtx-5070-g5070-12v2c"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword=rtx_5070_ti.name,
            gpu_model_id=msi_shadow_3x.id,
            brand=msi.name,
            model=msi_shadow_3x.variant_name,
            product_title="Placa De Vídeo Nvidia Geforce Msi Rtx5070ti 16gb",
            product_url="https://www.kabum.com.br/produto/857022/placa-de-video-nvidia-geforce-msi-rtx5070ti-16gb-gddr7-256its-shadow-3x-oc-912-v531-097"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword=rtx_5070_ti.name,
            gpu_model_id=gainward_phoenix.id,
            brand=gainward.name,
            model=gainward_phoenix.variant_name,
            product_title="Placa De Vídeo Gainward Rtx 5070 Ti Phoenix 16gb",
            product_url="https://www.kabum.com.br/produto/996236/placa-de-video-gainward-rtx-5070-ti-phoenix-16gb-gddr7"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword=rx_9070.name,
            gpu_model_id=xfx_swift_9070.id,
            brand=xfx.name,
            model=xfx_swift_9070.variant_name,
            product_title="Placa De Vídeo Xfx Swift Rx 9070 Oc Triple Fan Gaming Edition",
            product_url="https://www.kabum.com.br/produto/725937/placa-de-video-xfx-swift-rx-9070-oc-triple-fan-gaming-edition-with-amd-radeon-16gb-gddr6-hdmi-3xdp-rdna-4-rx-97swfb3b9"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword=rx_9070_xt.name,
            gpu_model_id=xfx_swift_9070_xt.id,
            brand=xfx.name,
            model=xfx_swift_9070_xt.variant_name,
            product_title="Placa de Vídeo Xfx Swift Rx 9070 Oc Triple Fan Gaming Edition",
            product_url="https://www.kabum.com.br/produto/725947/placa-de-video-xfx-swift-rx-9070-xt-triple-fan-gaming-edition-with-amd-radeon-16gb-gddr6-hdmi-3xdp-rdna-4-rx-97tswf3b9"
        )
    ]

    await repo.save_skus(skus)
    print(f"Successfully seeded {len(skus)} target URLs into prices.db! The Orchestrator will scrape these on its next tick.")

if __name__ == "__main__":
    asyncio.run(seed())
