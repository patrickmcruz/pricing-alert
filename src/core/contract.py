from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class PriceContract(BaseModel):
    """
    Canonical representation of a scraped product.
    Every scraper must return validated instances of this model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)

    execution_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the scraping execution.",
    )

    store_name: str = Field(..., description="Standardized store identifier.")

    search_keyword: str = Field(..., description="Keyword used to perform the search.")

    product_title: str = Field(
        ..., description="Full product title extracted from the retailer."
    )

    product_url: HttpUrl = Field(..., description="Absolute HTTPS product URL.")

    price_cash: Decimal = Field(..., description="Cash price in Brazilian Real (BRL).")

    price_installments: Decimal | None = Field(
        default=None, description="Installment price when available."
    )

    installment_count: int | None = Field(
        default=None, description="Maximum number of credit card installments (e.g., 10)."
    )

    currency: str = Field(..., description="Currency code (e.g., 'BRL', 'USD')")
    parser_version: str = Field(..., description="Version of the parser used to extract this data")
    is_available: bool = Field(
        ...,
        description="Indicates whether the product is currently available for purchase.",
    )

    brand: str | None = Field(default=None, description="Product brand name.")

    model: str | None = Field(default=None, description="Product model identifier.")

    discount: Decimal | None = Field(default=None, description="Discount amount applied.")

    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the record was created.",
    )

    produto_id: str | None = Field(
        default=None,
        description="FK into the catalog's produto table. Nullable: historical rows "
        "predate the catalog, and any code path without a resolved SKU won't have one.",
    )


class StoreConfig(BaseModel):
    """
    Store execution configuration.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    store_name: str

    target_keywords: List[str] = Field(default_factory=list)

    cron_times: List[str] = Field(
        ...,
        min_length=1,
        description="Daily execution schedule using the 24-hour 'HH:MM' format.",
    )

    enabled: bool = Field(
        default=True,
        description="Whether this store should be scheduled. If True but no scraper "
        "is registered for it, PriceEngine.build_schedule raises MissingScraperError.",
    )

class ProductSKU(BaseModel):
    """
    Discovered SKU mapping for the tracker.

    `produto_id` is the FK into the catalog (src/core/catalog.py) and is
    what actually gets persisted for an anuncio row. `brand`/`model` are
    populated by the repository at read time (joined from the catalog) for
    convenience - they're not written directly to storage, so don't hand-set
    them without a matching produto_id resolved via CatalogRepository.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    store_name: str
    search_keyword: str
    product_url: HttpUrl
    produto_id: str
    brand: str | None = None
    model: str | None = None
    product_title: str


class TargetUrlEntry(BaseModel):
    """
    A row in the `target_urls` table (src/db/schema.py) - the raw manifest of
    record DiscoveryEngine reads from, replacing data/target_urls.json (see
    specs/target-urls-table/spec.md). Free-text brand/model, same as the old
    JSON rows: DiscoveryEngine._resolve_catalog() is what turns these into a
    real Produto, not this model. Distinct from LegacyTargetUrlRow, which
    describes an already-resolved listings row that's merely missing its
    produto_id - a different table, a different repair concern.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    store_name: str
    search_keyword: str
    product_url: str
    brand: str | None = None
    model: str | None = None
    product_title: str | None = None


class LegacyTargetUrlRow(BaseModel):
    """
    An anuncio row still carrying its pre-catalog free-text brand/model
    instead of a resolved produto_id. Only used by
    DiscoveryEngine._backfill_existing_rows to resolve/create the matching
    catalog entry for rows written before the catalog existed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_url: str
    store_name: str
    search_keyword: str
    brand: str | None = None
    model: str | None = None
    product_title: str
