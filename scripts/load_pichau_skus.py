import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from src.core.catalog import GPU_CATEGORY_SLUG, ChipMaker, infer_chip_maker
from src.core.config import settings
from src.core.contract import ProductSKU
from src.db.schema import initialize_schema as initialize_db_schema
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository
from src.repositories.postgres_repository import PostgresPriceRepository


async def load_pichau_skus() -> None:
    await initialize_db_schema(settings.db_dsn)

    catalog_repo = PostgresCatalogRepository(dsn=settings.db_dsn)
    repo = PostgresPriceRepository(dsn=settings.db_dsn)

    categoria = await catalog_repo.get_or_create_categoria("GPU", GPU_CATEGORY_SLUG)
    marca = await catalog_repo.get_or_create_marca("MSI")

    async def produto(variant: str, chipset: str) -> object:
        return await catalog_repo.get_or_create_produto(
            marca.id,
            categoria.id,
            variant,
            specs={"chipset": chipset, "chip_maker": infer_chip_maker(chipset).value},
        )

    products = {
        "rtx 5070": await produto("GeForce RTX 5070", "rtx 5070"),
        "rtx 5070 ti": await produto("GeForce RTX 5070 Ti", "rtx 5070 ti"),
    }

    skus = [
        ProductSKU(
            store_name="pichau",
            search_keyword="rtx 5070",
            produto_id=products["rtx 5070"].id,
            brand="MSI",
            model=products["rtx 5070"].nome,
            product_title="Placa de vídeo MSI GeForce RTX 5070",
            product_url="https://www.pichau.com.br/placa-de-video-msi-geforce-rtx-5070-12gb",
        ),
        ProductSKU(
            store_name="pichau",
            search_keyword="rtx 5070 ti",
            produto_id=products["rtx 5070 ti"].id,
            brand="MSI",
            model=products["rtx 5070 ti"].nome,
            product_title="Placa de vídeo MSI GeForce RTX 5070 Ti 16GB",
            product_url="https://www.pichau.com.br/placa-de-video-msi-geforce-rtx-5070-ti-16gb",
        ),
    ]

    await repo.save_skus(skus)
    print(f"Loaded {len(skus)} Pichau SKU(s) into the database.")


if __name__ == "__main__":
    asyncio.run(load_pichau_skus())
