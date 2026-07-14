from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Store(BaseModel):
    """A retailer this app tracks prices at, e.g. kabum, mercado-livre."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    slug: str
    display_name: str
    base_url: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
