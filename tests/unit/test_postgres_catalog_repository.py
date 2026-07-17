import pytest

from src.core.catalog import GPU_CATEGORY_SLUG, ChipMaker
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository


@pytest.fixture
async def catalog(db_dsn):
    return PostgresCatalogRepository(db_dsn)


@pytest.fixture
async def categoria_id(catalog):
    categoria = await catalog.get_or_create_categoria("GPU", GPU_CATEGORY_SLUG)
    return categoria.id


@pytest.mark.asyncio
async def test_get_or_create_marca_dedupes_case_insensitively(catalog):
    first = await catalog.get_or_create_marca("MSI")
    second = await catalog.get_or_create_marca("msi")

    assert first.id == second.id
    assert first.nome == "MSI"  # first-seen casing wins

    marcas = await catalog.list_marcas()
    assert len(marcas) == 1


@pytest.mark.asyncio
async def test_get_or_create_categoria_dedupes_by_slug(catalog):
    first = await catalog.get_or_create_categoria("GPU", GPU_CATEGORY_SLUG)
    second = await catalog.get_or_create_categoria("Placas de Vídeo", GPU_CATEGORY_SLUG)

    assert first.id == second.id

    categorias = await catalog.list_categorias()
    assert len(categorias) == 1


@pytest.mark.asyncio
async def test_get_or_create_produto_dedupes_case_insensitively(catalog, categoria_id):
    marca = await catalog.get_or_create_marca("MSI")
    specs = {"chipset": "rtx 5070 ti", "chip_maker": ChipMaker.NVIDIA.value}

    first = await catalog.get_or_create_produto(marca.id, categoria_id, "Shadow 2X OC", specs=specs)
    second = await catalog.get_or_create_produto(marca.id, categoria_id, "shadow 2x oc", specs=specs)

    assert first.id == second.id


@pytest.mark.asyncio
async def test_get_or_create_produto_distinguishes_different_variants(catalog, categoria_id):
    marca = await catalog.get_or_create_marca("MSI")
    specs = {"chipset": "rtx 5070 ti"}

    shadow = await catalog.get_or_create_produto(marca.id, categoria_id, "Shadow 2X OC", specs=specs)
    ventus = await catalog.get_or_create_produto(marca.id, categoria_id, "Ventus 2X OC", specs=specs)

    assert shadow.id != ventus.id


@pytest.mark.asyncio
async def test_get_or_create_produto_distinguishes_different_chipsets(catalog, categoria_id):
    marca = await catalog.get_or_create_marca("MSI")

    a = await catalog.get_or_create_produto(
        marca.id, categoria_id, "Shadow 2X OC", specs={"chipset": "rtx 5070"}
    )
    b = await catalog.get_or_create_produto(
        marca.id, categoria_id, "Shadow 2X OC", specs={"chipset": "rtx 5070 ti"}
    )

    assert a.id != b.id


@pytest.mark.asyncio
async def test_get_produto_returns_none_for_unknown_id(catalog):
    assert await catalog.get_produto("00000000-0000-0000-0000-000000000000") is None


@pytest.mark.asyncio
async def test_list_produtos_resolved_joins_marca_and_categoria_names(catalog, categoria_id):
    marca = await catalog.get_or_create_marca("MSI")
    produto = await catalog.get_or_create_produto(
        marca.id, categoria_id, "Shadow 2X OC", specs={"chipset": "rtx 5070 ti"}
    )

    resolved = await catalog.list_produtos_resolved(categoria_slug=GPU_CATEGORY_SLUG)

    assert len(resolved) == 1
    assert resolved[0].id == produto.id
    assert resolved[0].marca_nome == "MSI"
    assert resolved[0].categoria_nome == "GPU"
    assert resolved[0].nome == "Shadow 2X OC"
    assert resolved[0].specs["chipset"] == "rtx 5070 ti"
