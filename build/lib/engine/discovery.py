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
        Runs the discovery process for all configs.
        """
        logger.info("Starting Discovery Engine run...")
        for config in configs:
            spider = self.spiders.get(config.store_name)
            if not spider:
                logger.warning("No spider found for %s", config.store_name)
                continue
                
            client = None
            try:
                if hasattr(self.client_factory, "create"):
                    client = await self.client_factory.create(spider)
                
                for keyword in config.target_keywords:
                    try:
                        skus = await spider.discover(keyword, client)
                        if skus:
                            await self.repository.save_skus(skus)
                    except Exception as e:
                        logger.error("Spider %s failed on keyword %s: %s", config.store_name, keyword, e)
            except Exception as e:
                logger.error("Failed to run discovery for %s: %s", config.store_name, e)
            finally:
                if client and hasattr(self.client_factory, "close"):
                    try:
                        await self.client_factory.close(client)
                    except Exception as e:
                        logger.error("Failed to close client: %s", e)
        
        logger.info("Discovery run complete.")
