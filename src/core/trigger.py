from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class TriggerStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerRequest(BaseModel):
    """
    A "run this now" request created by the dashboard (which has no browser
    of its own) and consumed by the orchestrator process (which does) - see
    TriggerProcessor. store_name=None means "run every registered scraper".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: UUID = Field(default_factory=uuid4)
    store_name: Optional[str] = None
    status: TriggerStatus = TriggerStatus.PENDING
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
