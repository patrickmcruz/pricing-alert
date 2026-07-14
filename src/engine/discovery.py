import json
import logging
import os

from src.core.contract import ProductSKU, StoreConfig
from src.repositories.base_repository import PriceRepository

logger = logging.getLogger(__name__)

DEFAULT_TARGET_URLS_PATH = os.path.join("data", "target_urls.json")


class DiscoveryEngine:
    """
    Coordinates the discovery of SKUs across target stores.

    Currently backed by a static manifest (`target_urls.json`) rather than
    live search-grid crawling; see .agents/AGENTS.md for the rationale.
    """

    def __init__(
        self,
        repository: PriceRepository,
        target_urls_path: str = DEFAULT_TARGET_URLS_PATH,
    ):
        self.repository = repository
        self.target_urls_path = target_urls_path

    async def run_discovery(self, configs: list[StoreConfig]) -> None:
        """
        Runs the discovery process by loading static URLs from the target manifest.
        """
        logger.info("Starting Discovery Engine run (Static Mode)...")

        if not os.path.exists(self.target_urls_path):
            logger.warning("File %s not found. Skipping discovery.", self.target_urls_path)
            return

        try:
            with open(self.target_urls_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            skus = [
                ProductSKU(
                    store_name=item["store_name"],
                    search_keyword=item["search_keyword"],
                    product_url=item["product_url"],
                    brand=item.get("brand"),
                    model=item.get("model"),
                    product_title=item.get("product_title", "Unknown"),
                )
                for item in data
            ]

            if skus:
                await self.repository.save_skus(skus)
                logger.info("Saved %d static SKUs from %s", len(skus), self.target_urls_path)
            else:
                logger.warning("No SKUs found in %s", self.target_urls_path)
        except Exception as e:
            logger.error("Failed to load static URLs from %s: %s", self.target_urls_path, e)

        logger.info("Discovery run complete.")
