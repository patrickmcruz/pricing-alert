import json
import logging
import os

from src.core.catalog import Brand, GpuChipset, GpuModel, infer_chip_maker
from src.core.contract import ProductSKU, StoreConfig
from src.repositories.base_repository import PriceRepository
from src.repositories.catalog_repository import CatalogRepository

logger = logging.getLogger(__name__)

DEFAULT_TARGET_URLS_PATH = os.path.join("data", "target_urls.json")

# search_keyword -> canonical chipset name. Keeps spelling/noise variations
# ("rx 9070 oc" is search noise, not part of the chipset) from becoming
# different GpuChipset rows.
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
    ) -> tuple[GpuChipset, Brand, GpuModel]:
        """Resolves (creating if needed) the Brand/GpuChipset/GpuModel for a free-text entry."""
        chipset_name = _resolve_chipset_name(search_keyword)
        chipset = await self.catalog_repository.get_or_create_chipset(
            chipset_name, chip_maker=infer_chip_maker(chipset_name)
        )
        brand_entity = await self.catalog_repository.get_or_create_brand(brand or "Unknown")
        variant_name = model or product_title or "Unknown"
        gpu_model = await self.catalog_repository.get_or_create_gpu_model(
            brand_entity.id, chipset.id, variant_name
        )
        return chipset, brand_entity, gpu_model

    async def _backfill_existing_rows(self) -> None:
        """
        Resolves gpu_model_id for any target_urls row written before the
        catalog existed, using its legacy free-text brand/model/search_keyword.
        """
        legacy_rows = await self.repository.list_target_urls_missing_gpu_model()
        for row in legacy_rows:
            _, _, gpu_model = await self._resolve_catalog(
                row.search_keyword, row.brand, row.model, row.product_title
            )
            await self.repository.set_sku_gpu_model_id(row.product_url, gpu_model.id)
        if legacy_rows:
            logger.info("Backfilled gpu_model_id for %d legacy target_urls row(s).", len(legacy_rows))

    async def run_discovery(self, configs: list[StoreConfig]) -> None:
        """
        Runs the discovery process: backfills any legacy target_urls row missing
        a gpu_model_id, then loads static URLs from the target manifest.
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
                chipset, brand_entity, gpu_model = await self._resolve_catalog(
                    item["search_keyword"], item.get("brand"), item.get("model"), item.get("product_title")
                )
                skus.append(
                    ProductSKU(
                        store_name=item["store_name"],
                        search_keyword=chipset.name,
                        product_url=item["product_url"],
                        gpu_model_id=gpu_model.id,
                        brand=brand_entity.name,
                        model=gpu_model.variant_name,
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
