from typing import Dict, Type
from src.spiders.base_spider import BaseSpider

_SPIDER_REGISTRY: Dict[str, Type[BaseSpider]] = {}


def register_spider(store_name: str):
    """
    Decorator to register a concrete BaseSpider subclass under a store_name key.
    """
    def decorator(cls: Type[BaseSpider]) -> Type[BaseSpider]:
        _SPIDER_REGISTRY[store_name.lower()] = cls
        return cls

    return decorator


def get_registered_spiders() -> Dict[str, Type[BaseSpider]]:
    """
    Returns a copy of the registered spider mapping.
    """
    return dict(_SPIDER_REGISTRY)


def get_spider_class(store_name: str) -> Type[BaseSpider]:
    """
    Retrieves the registered spider class for a store_name key.
    Raises KeyError if no spider is registered for the store.
    """
    key = store_name.lower()
    if key not in _SPIDER_REGISTRY:
        raise KeyError(f"No spider registered for store '{store_name}'")
    return _SPIDER_REGISTRY[key]
