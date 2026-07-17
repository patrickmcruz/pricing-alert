import os
import pytest

# Ensure the test environment is loaded before any core modules
os.environ["APP_ENV"] = "test"

@pytest.fixture(autouse=True)
def setup_test_env():
    """Ensure tests always use the test environment."""
    os.environ["APP_ENV"] = "test"


# Tables in FK-safe truncation order (children before/with parents via CASCADE).
_ALL_TABLES = [
    "alert_events", "alert_rules", "trigger_requests", "price_observations",
    "listing_runs", "scraper_runs", "listings", "products", "brands",
    "categories", "stores",
]


@pytest.fixture
async def db_dsn():
    """
    Every test shares the single `pricing_test` Postgres database (see
    docker-compose.yml's db service, which creates it via
    scripts/init_test_db.sql) rather than getting its own file/database -
    truncating all tables before each test is what gives them isolation
    instead. initialize_schema is idempotent (CREATE TABLE IF NOT EXISTS),
    so calling it per-test is cheap and guarantees a fresh schema even the
    first time this suite runs.
    """
    from src.core.config import settings
    from src.db.schema import connect, initialize_schema

    dsn = settings.db_dsn
    await initialize_schema(dsn)
    async with connect(dsn) as db:
        await db.execute(f"TRUNCATE {', '.join(_ALL_TABLES)} RESTART IDENTITY CASCADE")
    return dsn


async def make_produto_id(
    dsn: str,
    brand: str = "TestBrand",
    chipset: str = "rtx 5070",
    variant: str = "Test Variant",
) -> str:
    """
    Resolves (creating if needed) a real Marca/Categoria/Produto in the given
    database and returns the Produto id. Tests that persist a ProductSKU
    through PostgresPriceRepository (whose reads JOIN against the catalog
    tables) need a real produto_id, not a placeholder string, or
    get_target_skus/list_all_skus will silently filter the row out.
    """
    from src.core.catalog import GPU_CATEGORY_SLUG
    from src.repositories.postgres_catalog_repository import PostgresCatalogRepository

    catalog = PostgresCatalogRepository(dsn)
    categoria = await catalog.get_or_create_categoria("GPU", GPU_CATEGORY_SLUG)
    marca = await catalog.get_or_create_marca(brand)
    produto = await catalog.get_or_create_produto(
        marca.id, categoria.id, variant, specs={"chipset": chipset}
    )
    return produto.id
