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
    should produce an AlertEvent. Filters (store_name/search_keyword/produto_id)
    are optional - None means "match any".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: UUID = Field(default_factory=uuid4)
    store_id: Optional[str] = None
    store_name: Optional[str] = None  # resolved/joined from loja.slug at read time for matching+display, like ProductSKU.brand/model - never hand-set without a matching store_id
    produto_id: Optional[str] = None
    search_keyword: Optional[str] = None
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
        if self.produto_id and price.produto_id != self.produto_id:
            return False
        return True


class AlertEvent(BaseModel):
    """A rule that fired for a specific scraped price."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    rule_id: UUID
    coleta_preco_id: str
    price: PriceContract
    reason: str
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
