import os
import pytest

# Ensure the test environment is loaded before any core modules
os.environ["APP_ENV"] = "test"

@pytest.fixture(autouse=True)
def setup_test_env():
    """Ensure tests always use the test environment."""
    os.environ["APP_ENV"] = "test"


async def make_gpu_model_id(
    db_path: str,
    brand: str = "TestBrand",
    chipset: str = "rtx 5070",
    variant: str = "Test Variant",
) -> str:
    """
    Resolves (creating if needed) a real Brand/GpuChipset/GpuModel in the given
    db and returns the GpuModel id. Tests that persist a ProductSKU through
    SQLitePriceRepository (whose reads JOIN against the catalog tables) need a
    real gpu_model_id, not a placeholder string, or get_target_skus/list_all_skus
    will silently filter the row out.
    """
    from src.db.schema import initialize_schema as initialize_db_schema
    from src.repositories.sqlite_catalog_repository import SQLiteCatalogRepository

    await initialize_db_schema(db_path)
    catalog = SQLiteCatalogRepository(db_path)
    brand_entity = await catalog.get_or_create_brand(brand)
    chipset_entity = await catalog.get_or_create_chipset(chipset)
    gpu_model = await catalog.get_or_create_gpu_model(brand_entity.id, chipset_entity.id, variant)
    return gpu_model.id
