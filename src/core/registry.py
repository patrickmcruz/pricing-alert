from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from src.core.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

_SCRAPER_REGISTRY: dict[str, "BaseScraper"] = {}

T = TypeVar("T", bound="BaseScraper")


def register_scraper(cls: type[T]) -> type[T]:
    """
    Class decorator that self-registers a BaseScraper subclass.

    Instantiates the class once (concrete scrapers take no constructor
    arguments) and stores the instance keyed by its store_name, so the
    composition root (main.py) never needs to import concrete scrapers
    by name.
    """
    instance = cls()  # type: ignore[call-arg]  # concrete scrapers are no-arg by convention
    if instance.store_name in _SCRAPER_REGISTRY:
        raise ValueError(
            f"Duplicate scraper registration for store '{instance.store_name}' "
            f"(already registered by {_SCRAPER_REGISTRY[instance.store_name].__class__.__name__})"
        )
    _SCRAPER_REGISTRY[instance.store_name] = instance
    logger.debug("Auto-registered scraper for store: %s", instance.store_name)
    return cls


def get_registered_scrapers() -> dict[str, "BaseScraper"]:
    """Returns a copy of the store_name -> scraper instance registry."""
    return dict(_SCRAPER_REGISTRY)
