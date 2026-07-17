import asyncio
import os
import sys

# Ensure src module is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.db.schema import initialize_schema as initialize_db_schema
from src.repositories.postgres_repository import PostgresPriceRepository
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository

async def seed():
    from src.core.config import settings
    from src.core.catalog import GPU_CATEGORY_SLUG, ChipMaker
    print(f"Seeding database at {settings.db_dsn} with mock data from fixtures...")
    dsn = settings.db_dsn

    from src.core.contract import ProductSKU

    await initialize_db_schema(dsn)
    repo = PostgresPriceRepository(dsn)
    catalog = PostgresCatalogRepository(dsn)

    # Resolve marca/categoria/produto through the catalog before seeding SKUs.
    categoria = await catalog.get_or_create_categoria("GPU", GPU_CATEGORY_SLUG)
    msi = await catalog.get_or_create_marca("MSI")
    gainward = await catalog.get_or_create_marca("Gainward")
    xfx = await catalog.get_or_create_marca("xfx")

    async def produto(marca, chipset: str, chip_maker: ChipMaker, variant: str):
        return await catalog.get_or_create_produto(
            marca.id, categoria.id, variant,
            specs={"chipset": chipset, "chip_maker": chip_maker.value},
        )

    # "oc" in "rx 9070 oc" is search noise, not part of the chipset - canonical name is "rx 9070".
    msi_shadow_2x = await produto(msi, "rtx 5070", ChipMaker.NVIDIA, "Shadow 2X OC")
    msi_ventus_2x = await produto(msi, "rtx 5070", ChipMaker.NVIDIA, "Ventus 2X OC")
    msi_shadow_3x = await produto(msi, "rtx 5070 ti", ChipMaker.NVIDIA, "Shadow 3X OC")
    gainward_phoenix = await produto(gainward, "rtx 5070 ti", ChipMaker.NVIDIA, "Phoenix")
    xfx_swift_9070 = await produto(xfx, "rx 9070", ChipMaker.AMD, "swift")
    xfx_swift_9070_xt = await produto(xfx, "rx 9070 xt", ChipMaker.AMD, "swift")

    # Seed Target URLs (Spiders)
    skus = [
        ProductSKU(
            store_name="kabum",
            search_keyword="rtx 5070",
            produto_id=msi_shadow_2x.id,
            brand=msi.nome,
            model=msi_shadow_2x.nome,
            product_title="Placa De Video Msi Rtx 5070 12gb Gddr7",
            product_url="https://www.kabum.com.br/produto/875474/placa-de-video-msi-rtx-5070-12gb-gddr7-192-bits-shadow-2x-oc-912-v532-011"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword="rtx 5070",
            produto_id=msi_ventus_2x.id,
            brand=msi.nome,
            model=msi_ventus_2x.nome,
            product_title="Placa De Vídeo Msi Geforce Rtx 5070 12g Ventus 2x Oc",
            product_url="https://www.kabum.com.br/produto/725587/placa-de-video-msi-geforce-rtx-5070-12g-ventus-2x-oc-12-gb-gddr7-28gbps-nvidia-geforce-rtx-5070-g5070-12v2c"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword="rtx 5070 ti",
            produto_id=msi_shadow_3x.id,
            brand=msi.nome,
            model=msi_shadow_3x.nome,
            product_title="Placa De Vídeo Nvidia Geforce Msi Rtx5070ti 16gb",
            product_url="https://www.kabum.com.br/produto/857022/placa-de-video-nvidia-geforce-msi-rtx5070ti-16gb-gddr7-256its-shadow-3x-oc-912-v531-097"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword="rtx 5070 ti",
            produto_id=gainward_phoenix.id,
            brand=gainward.nome,
            model=gainward_phoenix.nome,
            product_title="Placa De Vídeo Gainward Rtx 5070 Ti Phoenix 16gb",
            product_url="https://www.kabum.com.br/produto/996236/placa-de-video-gainward-rtx-5070-ti-phoenix-16gb-gddr7"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword="rx 9070",
            produto_id=xfx_swift_9070.id,
            brand=xfx.nome,
            model=xfx_swift_9070.nome,
            product_title="Placa De Vídeo Xfx Swift Rx 9070 Oc Triple Fan Gaming Edition",
            product_url="https://www.kabum.com.br/produto/725937/placa-de-video-xfx-swift-rx-9070-oc-triple-fan-gaming-edition-with-amd-radeon-16gb-gddr6-hdmi-3xdp-rdna-4-rx-97swfb3b9"
        ),
        ProductSKU(
            store_name="kabum",
            search_keyword="rx 9070 xt",
            produto_id=xfx_swift_9070_xt.id,
            brand=xfx.nome,
            model=xfx_swift_9070_xt.nome,
            product_title="Placa de Vídeo Xfx Swift Rx 9070 Oc Triple Fan Gaming Edition",
            product_url="https://www.kabum.com.br/produto/725947/placa-de-video-xfx-swift-rx-9070-xt-triple-fan-gaming-edition-with-amd-radeon-16gb-gddr6-hdmi-3xdp-rdna-4-rx-97tswf3b9"
        )
    ]

    await repo.save_skus(skus)
    print(f"Successfully seeded {len(skus)} target URLs into {dsn}! The Orchestrator will scrape these on its next tick.")

if __name__ == "__main__":
    asyncio.run(seed())
