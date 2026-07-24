import logging
from typing import Any

from src.core.catalog import GPU_CATEGORY_SLUG, Categoria, Marca, Produto
from src.core.contract import ProductSKU, StoreConfig
from src.core.title_parser import TitleParserRegistry
from src.repositories.base_repository import PriceRepository
from src.repositories.catalog_repository import CatalogRepository
from src.repositories.target_url_repository import TargetUrlRepository

logger = logging.getLogger(__name__)

_CHIPSET_ALIASES = {
    "rx 9070 oc": "rx 9070",
}


def _resolve_chipset_name(search_keyword: str) -> str:
    key = search_keyword.strip().lower()
    return _CHIPSET_ALIASES.get(key, key)


class DiscoveryEngine:
    """
    Coordinates the discovery of SKUs across target stores.

    Currently backed by a static manifest (the `target_urls` table, see
    specs/target-urls-table/spec.md) rather than live search-grid crawling;
    see .agents/AGENTS.md for the rationale.
    """

    def __init__(
        self,
        repository: PriceRepository,
        catalog_repository: CatalogRepository,
        target_url_repository: TargetUrlRepository,
    ):
        self.repository = repository
        self.catalog_repository = catalog_repository
        self.target_url_repository = target_url_repository

    async def _resolve_catalog(
        self,
        search_keyword: str,
        brand: str | None,
        model: str | None,
        product_title: str | None,
    ) -> tuple[Categoria, Marca, Produto]:
        """Resolves (creating if needed) the Categoria/Marca/Produto for a free-text entry.

        Every discovered SKU today is a GPU (static target_urls.json manifest);
        the chipset becomes a spec on the produto rather than its own table, so
        future categories (notebooks, geladeiras...) can reuse this same path
        with a different categoria/specs shape.
        """
        categoria = await self.catalog_repository.get_or_create_categoria("GPU", GPU_CATEGORY_SLUG)
        
        # Extract structured specs using TitleParserRegistry
        parsed_gpu = TitleParserRegistry.parse_gpu(product_title or model or "", search_keyword=search_keyword)
        brand_name = brand or parsed_gpu.chip_maker or "Unknown"
        marca = await self.catalog_repository.get_or_create_marca(brand_name)
        model_name = model or product_title or "Unknown"
        
        actual_chipset = parsed_gpu.chipset or _resolve_chipset_name(search_keyword)
        specs = parsed_gpu.to_dict()
        specs["chipset"] = actual_chipset
        
        produto = await self.catalog_repository.get_or_create_produto(
            marca_id=marca.id,
            categoria_id=categoria.id,
            nome=model_name,
            specs=specs,
            mpn=parsed_gpu.mpn,
            product_line=parsed_gpu.product_line,
            is_oc=parsed_gpu.is_oc,
        )
        return categoria, marca, produto

    async def _backfill_existing_rows(self) -> None:
        """
        Resolves produto_id for any anuncio row written before the catalog
        existed, using its legacy free-text brand/model/search_keyword.
        """
        legacy_rows = await self.repository.list_target_urls_missing_produto()
        for row in legacy_rows:
            _, _, produto = await self._resolve_catalog(
                row.search_keyword, row.brand, row.model, row.product_title
            )
            await self.repository.set_sku_produto_id(row.product_url, produto.id)
        if legacy_rows:
            logger.info("Backfilled produto_id for %d legacy anuncio row(s).", len(legacy_rows))

    async def run_discovery(self, configs: list[StoreConfig]) -> None:
        """
        Runs the discovery process: backfills any legacy anuncio row missing
        a produto_id, then loads static URLs from the target_urls manifest.
        """
        logger.info("Starting Discovery Engine run (Static Mode)...")

        await self._backfill_existing_rows()

        try:
            entries = await self.target_url_repository.list_all()

            skus = []
            for entry in entries:
                _, marca, produto = await self._resolve_catalog(
                    entry.search_keyword, entry.brand, entry.model, entry.product_title
                )
                skus.append(
                    ProductSKU(
                        store_name=entry.store_name,
                        search_keyword=produto.specs.get("chipset", entry.search_keyword),
                        product_url=entry.product_url,
                        produto_id=produto.id,
                        brand=marca.nome,
                        model=produto.nome,
                        product_title=entry.product_title or "Unknown",
                    )
                )

            if skus:
                await self.repository.save_skus(skus)
                logger.info("Saved %d static SKUs from target_urls.", len(skus))
            else:
                logger.warning("No rows in target_urls. Skipping discovery.")
        except Exception as e:
            logger.error("Failed to load static URLs from target_urls: %s", e)

        logger.info("Discovery run complete.")

    async def run_spider_discovery(
        self,
        keywords: list[str],
        category: str = "cpu",
        client_factories: dict[str, Any] | None = None,
    ) -> list[ProductSKU]:
        """
        Executes registered Store Spiders to discover new hardware SKUs for the given keywords and category.
        Idempotently persists discovered SKUs into target_urls and listings tables.
        """
        from src.spiders.registry import get_registered_spiders

        registered_spiders = get_registered_spiders()
        if not registered_spiders:
            logger.warning("No store spiders registered for dynamic discovery.")
            return []

        cat_title = category.upper()
        cat_slug = category.lower()
        categoria = await self.catalog_repository.get_or_create_categoria(cat_title, cat_slug)

        discovered_skus: list[ProductSKU] = []

        for keyword in keywords:
            for store_name, spider_cls in registered_spiders.items():
                spider = spider_cls()
                client_factory = client_factories.get(spider.transport_type) if client_factories else None
                if not client_factory:
                    logger.debug("No client factory provided for transport_type %r (store %s)", spider.transport_type, store_name)
                    continue

                try:
                    client = await client_factory.create(spider)
                    try:
                        found_skus = await spider.execute(keyword, category, client)
                        for d_sku in found_skus:
                            if category.lower() == "cpu":
                                parsed_cpu = TitleParserRegistry.parse_cpu(d_sku.product_title, keyword)
                                marca = await self.catalog_repository.get_or_create_marca(parsed_cpu.manufacturer)
                                produto = await self.catalog_repository.get_or_create_produto(
                                    marca_id=marca.id,
                                    categoria_id=categoria.id,
                                    nome=f"{parsed_cpu.model_family} {parsed_cpu.model_number}",
                                    specs=parsed_cpu.to_dict(),
                                    mpn=parsed_cpu.mpn,
                                )
                            else:
                                _, marca, produto = await self._resolve_catalog(
                                    keyword, d_sku.brand, d_sku.model, d_sku.product_title
                                )

                            real_keyword = str(produto.specs.get("chipset", keyword)).lower()
                            sku = ProductSKU(
                                store_name=store_name,
                                search_keyword=real_keyword,
                                product_url=d_sku.product_url,
                                produto_id=produto.id,
                                brand=marca.nome,
                                model=produto.nome,
                                product_title=d_sku.product_title,
                            )
                            discovered_skus.append(sku)
                    finally:
                        await client_factory.close(client)
                except Exception as e:
                    logger.error("Spider '%s' failed for keyword %r: %s", store_name, keyword, e)

        if discovered_skus:
            if self.target_url_repository:
                target_entries = [
                    TargetUrlEntry(
                        store_name=s.store_name,
                        search_keyword=s.search_keyword,
                        product_url=s.product_url,
                        brand=s.brand,
                        model=s.model,
                        product_title=s.product_title,
                    )
                    for s in discovered_skus
                ]
                await self.target_url_repository.upsert_many(target_entries)
            await self.repository.save_skus(discovered_skus)
            logger.info("Saved %d SKUs discovered by store spiders.", len(discovered_skus))

        return discovered_skus
