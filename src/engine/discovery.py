import logging

from src.core.catalog import GPU_CATEGORY_SLUG, Categoria, Marca, Produto, infer_chip_maker
from src.core.contract import ProductSKU, StoreConfig
from src.repositories.base_repository import PriceRepository
from src.repositories.catalog_repository import CatalogRepository
from src.repositories.target_url_repository import TargetUrlRepository

logger = logging.getLogger(__name__)

# search_keyword -> canonical chipset name. Keeps spelling/noise variations
# ("rx 9070 oc" is search noise, not part of the chipset) from becoming
# different produto.specs["chipset"] values.
_CHIPSET_ALIASES = {
    "rx 9070 oc": "rx 9070",
}


from src.core.title_parser import TitleParserRegistry


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
        chipset_name = _resolve_chipset_name(search_keyword)
        categoria = await self.catalog_repository.get_or_create_categoria("GPU", GPU_CATEGORY_SLUG)
        
        # Extract structured specs using TitleParserRegistry
        parsed_gpu = TitleParserRegistry.parse_gpu(product_title or model or "", search_keyword=chipset_name)
        brand_name = brand or parsed_gpu.brand_name or "Unknown"
        marca = await self.catalog_repository.get_or_create_marca(brand_name)
        model_name = model or product_title or "Unknown"
        
        specs = parsed_gpu.to_dict()
        specs["chipset"] = chipset_name
        
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
