import pytest

from src.core.catalog import ChipMaker
from src.db.schema import initialize_schema as initialize_db_schema
from src.repositories.sqlite_catalog_repository import SQLiteCatalogRepository


@pytest.fixture
async def catalog(tmp_path):
    db_path = str(tmp_path / "catalog_test.db")
    await initialize_db_schema(db_path)
    repository = SQLiteCatalogRepository(db_path)
    yield repository


@pytest.mark.asyncio
async def test_get_or_create_brand_dedupes_case_insensitively(catalog):
    first = await catalog.get_or_create_brand("MSI")
    second = await catalog.get_or_create_brand("msi")

    assert first.id == second.id
    assert first.name == "MSI"  # first-seen casing wins

    brands = await catalog.list_brands()
    assert len(brands) == 1


@pytest.mark.asyncio
async def test_get_or_create_chipset_dedupes_case_insensitively(catalog):
    first = await catalog.get_or_create_chipset("rtx 5070 ti", chip_maker=ChipMaker.NVIDIA)
    second = await catalog.get_or_create_chipset("RTX 5070 TI")

    assert first.id == second.id
    assert first.chip_maker == ChipMaker.NVIDIA

    chipsets = await catalog.list_chipsets()
    assert len(chipsets) == 1


@pytest.mark.asyncio
async def test_get_or_create_gpu_model_dedupes_case_insensitively(catalog):
    brand = await catalog.get_or_create_brand("MSI")
    chipset = await catalog.get_or_create_chipset("rtx 5070 ti")

    first = await catalog.get_or_create_gpu_model(brand.id, chipset.id, "Shadow 2X OC")
    second = await catalog.get_or_create_gpu_model(brand.id, chipset.id, "shadow 2x oc")

    assert first.id == second.id


@pytest.mark.asyncio
async def test_get_or_create_gpu_model_distinguishes_different_variants(catalog):
    brand = await catalog.get_or_create_brand("MSI")
    chipset = await catalog.get_or_create_chipset("rtx 5070 ti")

    shadow = await catalog.get_or_create_gpu_model(brand.id, chipset.id, "Shadow 2X OC")
    ventus = await catalog.get_or_create_gpu_model(brand.id, chipset.id, "Ventus 2X OC")

    assert shadow.id != ventus.id


@pytest.mark.asyncio
async def test_get_gpu_model_returns_none_for_unknown_id(catalog):
    assert await catalog.get_gpu_model("does-not-exist") is None


@pytest.mark.asyncio
async def test_list_gpu_models_resolved_joins_brand_and_chipset_names(catalog):
    brand = await catalog.get_or_create_brand("MSI")
    chipset = await catalog.get_or_create_chipset("rtx 5070 ti")
    gpu_model = await catalog.get_or_create_gpu_model(brand.id, chipset.id, "Shadow 2X OC")

    resolved = await catalog.list_gpu_models_resolved()

    assert len(resolved) == 1
    assert resolved[0].id == gpu_model.id
    assert resolved[0].brand_name == "MSI"
    assert resolved[0].chipset_name == "rtx 5070 ti"
    assert resolved[0].model_name == "Shadow 2X OC"
