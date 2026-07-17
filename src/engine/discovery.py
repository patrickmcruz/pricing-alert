import json
import logging
import os

from src.core.catalog import GPU_CATEGORY_SLUG, Categoria, Marca, Produto, infer_chip_maker
from src.core.config import settings
from src.core.contract import ProductSKU, StoreConfig
from src.repositories.base_repository import PriceRepository
from src.repositories.catalog_repository import CatalogRepository

logger = logging.getLogger(__name__)

DEFAULT_TARGET_URLS_PATH = settings.target_urls_path

# search_keyword -> canonical chipset name. Keeps spelling/noise variations
# ("rx 9070 oc" is search noise, not part of the chipset) from becoming
# different produto.specs["chipset"] values.
_CHIPSET_ALIASES = {
    "rx 9070 oc": "rx 9070",
}


def _resolve_chipset_name(search_keyword: str) -> str:
    key = search_keyword.strip().lower()
    return _CHIPSET_ALIASES.get(key, key)


class DiscoveryEngine:
    """
    Coordinates the discovery of SKUs across target stores.

    Currently backed by a static manifest (`target_urls.json`) rather than
    live search-grid crawling; see .agents/AGENTS.md for the rationale.
    """

    def __init__(
        self,
        repository: PriceRepository,
        catalog_repository: CatalogRepository,
        target_urls_path: str = DEFAULT_TARGET_URLS_PATH,
    ):
        self.repository = repository
        self.catalog_repository = catalog_repository
        self.target_urls_path = target_urls_path

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
        marca = await self.catalog_repository.get_or_create_marca(brand or "Unknown")
        model_name = model or product_title or "Unknown"
        specs = {"chipset": chipset_name, "chip_maker": infer_chip_maker(chipset_name).value}
        produto = await self.catalog_repository.get_or_create_produto(
            marca.id, categoria.id, model_name, specs=specs
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
        a produto_id, then loads static URLs from the target manifest.
        """
        logger.info("Starting Discovery Engine run (Static Mode)...")

        await self._backfill_existing_rows()

        if not os.path.exists(self.target_urls_path):
            logger.warning("File %s not found. Skipping discovery.", self.target_urls_path)
            return

        try:
            with open(self.target_urls_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            skus = []
            for item in data:
                _, marca, produto = await self._resolve_catalog(
                    item["search_keyword"], item.get("brand"), item.get("model"), item.get("product_title")
                )
                skus.append(
                    ProductSKU(
                        store_name=item["store_name"],
                        search_keyword=produto.specs.get("chipset", item["search_keyword"]),
                        product_url=item["product_url"],
                        produto_id=produto.id,
                        brand=marca.nome,
                        model=produto.nome,
                        product_title=item.get("product_title", "Unknown"),
                    )
                )

            if skus:
                await self.repository.save_skus(skus)
                logger.info("Saved %d static SKUs from %s", len(skus), self.target_urls_path)
            else:
                logger.warning("No SKUs found in %s", self.target_urls_path)
        except Exception as e:
            logger.error("Failed to load static URLs from %s: %s", self.target_urls_path, e)

        logger.info("Discovery run complete.")
