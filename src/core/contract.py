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

    currency: str = Field(default="BRL", description="ISO-4217 currency code.")

    is_available: bool = Field(
        ...,
        description="Indicates whether the product is currently available for purchase.",
    )

    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the record was created.",
    )


class StoreConfig(BaseModel):
    """
    Store execution configuration.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    store_name: str

    target_keywords: List[str] = Field(..., min_length=1)

    cron_times: List[str] = Field(
        ...,
        min_length=1,
        description="Daily execution schedule using the 24-hour 'HH:MM' format.",
    )
