# **ARTIFACT 4: BaseScraper Architecture (Test-Ready)**

## Overview

`BaseScraper` defines the common abstraction shared by every store implementation.

The architecture must strictly separate **network I/O**, **document parsing**, and **data normalization** to maximize testability, extensibility, and maintainability.

Network operations are responsible only for retrieving the raw document.

Parsing is responsible only for extracting structured information.

Normalization converts extracted data into validated `PriceContract` instances.

This separation allows parser unit tests to execute using static fixtures without requiring internet connectivity, browser automation, databases, or schedulers.

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List
import asyncio
import logging
import random

from src.core.contract import PriceContract


logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Base abstraction for all scraper implementations.

    Concrete scrapers should implement only document retrieval
    and parsing logic.
    """

    def __init__(
        self,
        store_name: str,
        base_url: str,
    ):
        self.store_name = store_name
        self.base_url = base_url

    async def apply_jitter(
        self,
        min_seconds: float = 3.0,
        max_seconds: float = 8.0,
    ) -> None:
        """
        Applies a randomized asynchronous delay to reduce
        deterministic request patterns.
        """
        await asyncio.sleep(random.uniform(min_seconds, max_seconds))

    @abstractmethod
    async def fetch(
        self,
        keyword: str,
        client: Any,
    ) -> str:
        """
        Performs only network I/O.

        Returns the raw document retrieved from the store.
        """

    @abstractmethod
    def parse(
        self,
        document: str,
        keyword: str,
    ) -> List[PriceContract]:
        """
        Parses the retrieved document and returns validated
        PriceContract objects.

        This method must be deterministic and independently
        unit-testable using static fixtures.
        """

    async def execute(
        self,
        keyword: str,
        client: Any,
    ) -> List[PriceContract]:
        """
        Executes the complete scraping pipeline.
        """

        await self.apply_jitter()

        logger.info(
            "Starting scraper '%s' for keyword '%s'",
            self.store_name,
            keyword,
        )

        document = await self.fetch(keyword, client)

        if not document:
            return []

        return self.parse(document, keyword)
```

---

## **Implementation Requirements**

The agent must ensure that:

- `BaseScraper` remains an abstract base class (`ABC`).
- Every scraper inherits from `BaseScraper`.
- The Strategy Pattern is strictly followed.
- Network I/O, parsing, and orchestration remain completely separated.
- `fetch()` performs only network I/O.
- `parse()` performs only document parsing and data extraction.
- `parse()` never performs network requests.
- `execute()` coordinates jitter, retrieval, and parsing without containing business logic.
- Dependencies (HTTP clients or browser contexts) are injected into `fetch()` rather than instantiated internally.
- `parse()` is deterministic and fully testable using static fixtures.
- `parse()` always returns a `List[PriceContract]`; if no products are found, an empty list is returned.
- Scrapers never communicate directly with the persistence layer.
- Scrapers never instantiate schedulers, repositories, HTTP clients, or browser instances.
- Exceptions must be propagated as structured errors without terminating the orchestration engine.
- Every scraper must include parser unit tests using the fixtures defined in **Artifact 6**.
- The base class remains independent of scheduling, persistence, dependency injection, and presentation logic.