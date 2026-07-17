import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from src.core.trigger import TriggerRequest, TriggerStatus
from src.db.schema import affected_rows, connect
from src.repositories.postgres_store_repository import get_or_create_store_id
from src.repositories.trigger_repository import TriggerRepository

logger = logging.getLogger(__name__)


class PostgresTriggerRepository(TriggerRepository):
    """PostgreSQL implementation of TriggerRepository, using the same database as prices."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    async def create_request(self, store_name: Optional[str] = None) -> UUID:
        request_id = uuid4()
        requested_at = datetime.now(timezone.utc)
        async with connect(self.dsn) as db:
            async with db.transaction():
                store_id = await get_or_create_store_id(db, store_name) if store_name else None
                await db.execute(
                    "INSERT INTO trigger_requests (id, loja_id, status, requested_at) VALUES ($1, $2, $3, $4)",
                    str(request_id), store_id, TriggerStatus.PENDING.value, requested_at,
                )
        return request_id

    async def get_pending_requests(self) -> List[TriggerRequest]:
        return await self._query_by_status([TriggerStatus.PENDING])

    async def get_active_requests(self) -> List[TriggerRequest]:
        return await self._query_by_status([TriggerStatus.PENDING, TriggerStatus.PROCESSING])

    async def mark_processing(self, request_id: UUID) -> None:
        await self._update_status(request_id, TriggerStatus.PROCESSING)

    async def mark_completed(self, request_id: UUID) -> None:
        await self._update_status(request_id, TriggerStatus.COMPLETED, set_processed_at=True)

    async def mark_failed(self, request_id: UUID, error_message: str) -> None:
        await self._update_status(
            request_id, TriggerStatus.FAILED, set_processed_at=True, error_message=error_message
        )

    async def fail_stale_processing(self, error_message: str) -> int:
        processed_at = datetime.now(timezone.utc)
        async with connect(self.dsn) as db:
            status = await db.execute(
                """
                UPDATE trigger_requests
                SET status = $1, processed_at = $2, error_message = $3
                WHERE status = $4
                """,
                TriggerStatus.FAILED.value, processed_at, error_message, TriggerStatus.PROCESSING.value,
            )
            count = affected_rows(status)
        if count:
            logger.warning("Marked %d orphaned 'processing' trigger request(s) as failed on startup.", count)
        return count

    async def _query_by_status(self, statuses: List[TriggerStatus]) -> List[TriggerRequest]:
        placeholders = ",".join(f"${i + 1}" for i in range(len(statuses)))
        async with connect(self.dsn) as db:
            rows = await db.fetch(
                f"""
                SELECT tr.*, l.slug AS store_slug FROM trigger_requests tr
                LEFT JOIN loja l ON l.id = tr.loja_id
                WHERE tr.status IN ({placeholders})
                ORDER BY tr.requested_at ASC
                """,
                *[s.value for s in statuses],
            )
        return [self._row_to_record(row) for row in rows]

    async def _update_status(
        self,
        request_id: UUID,
        status: TriggerStatus,
        set_processed_at: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        processed_at = datetime.now(timezone.utc) if set_processed_at else None
        async with connect(self.dsn) as db:
            await db.execute(
                """
                UPDATE trigger_requests
                SET status = $1, processed_at = COALESCE($2, processed_at), error_message = $3
                WHERE id = $4
                """,
                status.value, processed_at, error_message, str(request_id),
            )

    @staticmethod
    def _row_to_record(row) -> TriggerRequest:
        return TriggerRequest(
            request_id=row["id"],
            store_name=row["store_slug"],
            status=row["status"],
            requested_at=row["requested_at"],
            processed_at=row["processed_at"],
            error_message=row["error_message"],
        )
