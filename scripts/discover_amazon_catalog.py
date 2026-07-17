"""Amazon ASIN discovery helper: searches the SP-API Catalog Items API for each
configured GPU keyword (settings.default_gpus) in the Brazil marketplace and
saves matching ASINs as tracked SKUs, the same way manually adding a URL via
the "Gerenciar GPUs" dashboard page does.

There is no automated crawling in this repo (see .agents/AGENTS.md §5 - the
earlier live search-grid spider design was deprecated and removed); this
script is a manual, scoped, run-it-yourself helper, not a scheduled job.

Run manually: `python scripts/discover_amazon_catalog.py`. Requires
AMAZON_LWA_APP_CLIENT_ID/SECRET_KEY and AMAZON_SP_API_REFRESH_TOKEN in .env.
Review the results in the dashboard afterward - this only adds SKUs, it never
removes ones you've already curated.

Note: the *pricing* scraper (src/scrapers/amazon.py) no longer uses SP-API -
it scrapes product pages directly, since real SP-API pricing access needs a
production seller authorization this project doesn't have (see
src/scrapers/amazon_spapi.py). This script still works from the sandbox or a
production refresh token if you get one, purely for ASIN discovery via the
Catalog Items API - the URLs it saves are then scraped by the HTML scraper.
"""
import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

import httpx

from src.core.catalog import GPU_CATEGORY_SLUG, infer_chip_maker
from src.core.config import settings
from src.core.contract import ProductSKU
from src.db.schema import initialize_schema as initialize_db_schema
from src.repositories.postgres_catalog_repository import PostgresCatalogRepository
from src.repositories.postgres_repository import PostgresPriceRepository
from src.scrapers.amazon_spapi import AmazonSPAPIScraper

SEARCH_URL_PATH = "/catalog/2022-04-01/items"
MAX_RESULTS_PER_KEYWORD = 10


async def _search_asins(client: httpx.AsyncClient, token: str, keyword: str) -> list[dict]:
    response = await client.get(
        f"{settings.amazon_spapi_base_url}{SEARCH_URL_PATH}",
        headers={"x-amz-access-token": token, "Content-Type": "application/json"},
        params={
            "marketplaceIds": settings.amazon_marketplace_id,
            "keywords": keyword,
            "includedData": "summaries",
        },
    )
    if response.status_code != 200:
        print(f"  Search failed for '{keyword}': {response.status_code} {response.text}")
        return []
    return response.json().get("items", [])[:MAX_RESULTS_PER_KEYWORD]


async def discover():
    await initialize_db_schema(settings.db_dsn)
    price_repo = PostgresPriceRepository(dsn=settings.db_dsn)
    catalog_repo = PostgresCatalogRepository(dsn=settings.db_dsn)

    scraper = AmazonSPAPIScraper()
    keywords = settings.default_gpus

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        token = await scraper._get_access_token(client)
        if not token:
            print("Could not authenticate with SP-API - check AMAZON_* credentials in .env.")
            return

        categoria = await catalog_repo.get_or_create_categoria("GPU", GPU_CATEGORY_SLUG)

        skus: list[ProductSKU] = []
        for keyword in keywords:
            print(f"Searching Amazon.com.br catalog for '{keyword}'...")
            items = await _search_asins(client, token, keyword)

            chipset_name = keyword.strip().lower()
            chip_maker = infer_chip_maker(keyword)

            for item in items:
                asin = item.get("asin")
                summaries = item.get("summaries", [])
                if not asin or not summaries:
                    continue

                summary = summaries[0]
                title = summary.get("itemName", asin)
                brand_name = summary.get("brand", "Unknown")

                marca = await catalog_repo.get_or_create_marca(brand_name)
                produto = await catalog_repo.get_or_create_produto(
                    marca.id, categoria.id, title,
                    specs={"chipset": chipset_name, "chip_maker": chip_maker.value},
                )

                skus.append(
                    ProductSKU(
                        store_name="amazon",
                        search_keyword=chipset_name,
                        product_url=f"https://www.amazon.com.br/dp/{asin}",
                        produto_id=produto.id,
                        brand=marca.nome,
                        model=produto.nome,
                        product_title=title,
                    )
                )
                print(f"  Found {asin}: {title} ({brand_name})")

    if skus:
        await price_repo.save_skus(skus)
        print(f"\nSaved {len(skus)} Amazon SKU(s). Review/edit them in the 'Gerenciar GPUs' dashboard page.")
    else:
        print("\nNo Amazon SKUs found for the configured keywords.")


if __name__ == "__main__":
    asyncio.run(discover())
