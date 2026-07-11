import logging
from typing import Dict, Iterable

from src.core.contract import StoreConfig
from src.repositories.base_repository import PriceRepository
from src.spiders.base_spider import BaseSpider

logger = logging.getLogger(__name__)

class DiscoveryEngine:
    """
    Coordinates the discovery of SKUs across target stores.
    """
    def __init__(self, repository: PriceRepository, client_factory):
        self.repository = repository
        self.client_factory = client_factory
        self.spiders: Dict[str, BaseSpider] = {}

    def register_spider(self, spider: BaseSpider) -> None:
        self.spiders[spider.store_name] = spider
        logger.info("Registered spider for store: %s", spider.store_name)

    def register_spiders(self, spiders: Iterable[BaseSpider]) -> None:
        for spider in spiders:
            self.register_spider(spider)

    async def run_discovery(self, configs: list[StoreConfig]) -> None:
        """
        Runs the discovery process by loading static URLs from data/target_urls.json.
        """
        import json
        import os
        from src.core.contract import ProductSKU
        
        logger.info("Starting Discovery Engine run (Static Mode)...")
        target_file = "data/target_urls.json"
        
        if not os.path.exists(target_file):
            logger.warning("File %s not found. Skipping discovery.", target_file)
            return

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            skus = []
            for item in data:
                skus.append(ProductSKU(
                    store_name=item["store_name"],
                    search_keyword=item["search_keyword"],
                    product_url=item["product_url"],
                    brand=item.get("brand"),
                    model=item.get("model"),
                    product_title=item.get("product_title", "Unknown")
                ))
                
            if skus:
                await self.repository.save_skus(skus)
                logger.info("Saved %d static SKUs from %s", len(skus), target_file)
            else:
                logger.warning("No SKUs found in %s", target_file)
        except Exception as e:
            logger.error("Failed to load static URLs from %s: %s", target_file, e)
            
        logger.info("Discovery run complete.")
