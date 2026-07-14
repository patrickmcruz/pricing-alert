from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.core.contract import PriceContract


class ThresholdType(str, Enum):
    ABSOLUTE_PRICE = "absolute_price"
    PERCENT_DROP = "percent_drop"
    ANY_DROP = "any_drop"


class AlertRule(BaseModel):
    """
    A user-defined condition that, when matched by an incoming PriceContract,
    should produce an AlertEvent. Filters (store_name/search_keyword/brand/model)
    are optional - None means "match any".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: UUID = Field(default_factory=uuid4)
    store_name: Optional[str] = None
    search_keyword: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    threshold_type: ThresholdType
    threshold_value: Optional[Decimal] = Field(
        default=None,
        description="Required for ABSOLUTE_PRICE (max price) and PERCENT_DROP "
        "(minimum % drop, e.g. 10 for 10%). Ignored for ANY_DROP.",
    )
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def matches(self, price: PriceContract) -> bool:
        if self.store_name and price.store_name != self.store_name:
            return False
        if self.search_keyword and price.search_keyword != self.search_keyword:
            return False
        # Case-insensitive: brand/model canonicalization (see src/core/catalog.py)
        # can change display casing over time (e.g. "xfx" -> "XFX"), and a rule
        # saved before that shouldn't silently stop matching.
        if self.brand and (price.brand or "").strip().lower() != self.brand.strip().lower():
            return False
        if self.model and (price.model or "").strip().lower() != self.model.strip().lower():
            return False
        return True


class AlertEvent(BaseModel):
    """A rule that fired for a specific scraped price."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    rule_id: UUID
    price: PriceContract
    reason: str
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
