from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.core.trigger import TriggerRequest


class TriggerRepository(ABC):
    """
    Abstract interface for the "run now" request queue: the dashboard
    (which has no browser of its own) writes requests here, and the
    orchestrator (which does) polls and executes them via TriggerProcessor.
    """

    @abstractmethod
    async def initialize_schema(self) -> None:
        """Creates the trigger_requests table if it doesn't exist."""

    @abstractmethod
    async def create_request(self, store_name: Optional[str] = None) -> UUID:
        """Enqueues a request. store_name=None means 'run every scraper'."""

    @abstractmethod
    async def get_pending_requests(self) -> List[TriggerRequest]:
        """Returns requests still waiting to be picked up, oldest first."""

    @abstractmethod
    async def get_active_requests(self) -> List[TriggerRequest]:
        """Returns requests that are pending or currently processing."""

    @abstractmethod
    async def mark_processing(self, request_id: UUID) -> None: ...

    @abstractmethod
    async def mark_completed(self, request_id: UUID) -> None: ...

    @abstractmethod
    async def mark_failed(self, request_id: UUID, error_message: str) -> None: ...

    @abstractmethod
    async def fail_stale_processing(self, error_message: str) -> int:
        """
        Marks any request still 'processing' as failed. Meant to be called once
        at startup: a 'processing' row can only be legitimate if the orchestrator
        process that set it is still alive, so after a restart every such row is
        provably orphaned - left alone, it would block its store's (or all
        stores', for store_name=None) trigger button forever. Returns the count
        of rows reset.
        """

