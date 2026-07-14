import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

import aiosqlite

from src.core.trigger import TriggerRequest, TriggerStatus
from src.db.schema import connect
from src.repositories.sqlite_store_repository import get_or_create_store_id
from src.repositories.trigger_repository import TriggerRepository

logger = logging.getLogger(__name__)


class SQLiteTriggerRepository(TriggerRepository):
    """SQLite implementation of TriggerRepository, using the same db file as prices."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def create_request(self, store_name: Optional[str] = None) -> UUID:
        request_id = uuid4()
        requested_at = datetime.now(timezone.utc)
        async with connect(self.db_path) as db:
            store_id = await get_or_create_store_id(db, store_name) if store_name else None
            await db.execute(
                """
                INSERT INTO trigger_requests (id, store_id, status, requested_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(request_id), store_id, TriggerStatus.PENDING.value, requested_at.isoformat()),
            )
            await db.commit()
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
        processed_at = datetime.now(timezone.utc).isoformat()
        async with connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE trigger_requests
                SET status = ?, processed_at = ?, error_message = ?
                WHERE status = ?
                """,
                (TriggerStatus.FAILED.value, processed_at, error_message, TriggerStatus.PROCESSING.value),
            )
            await db.commit()
            count = cursor.rowcount
        if count:
            logger.warning("Marked %d orphaned 'processing' trigger request(s) as failed on startup.", count)
        return count

    async def _query_by_status(self, statuses: List[TriggerStatus]) -> List[TriggerRequest]:
        placeholders = ",".join("?" for _ in statuses)
        async with connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"""
                SELECT tr.*, s.slug AS store_slug FROM trigger_requests tr
                LEFT JOIN stores s ON s.id = tr.store_id
                WHERE tr.status IN ({placeholders})
                ORDER BY tr.requested_at ASC
                """,
                [s.value for s in statuses],
            )
            rows = await cursor.fetchall()
        return [self._row_to_record(row) for row in rows]

    async def _update_status(
        self,
        request_id: UUID,
        status: TriggerStatus,
        set_processed_at: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        processed_at = datetime.now(timezone.utc).isoformat() if set_processed_at else None
        async with connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE trigger_requests
                SET status = ?, processed_at = COALESCE(?, processed_at), error_message = ?
                WHERE id = ?
                """,
                (status.value, processed_at, error_message, str(request_id)),
            )
            await db.commit()

    @staticmethod
    def _row_to_record(row: aiosqlite.Row) -> TriggerRequest:
        return TriggerRequest(
            request_id=row["id"],
            store_name=row["store_slug"],
            status=row["status"],
            requested_at=row["requested_at"],
            processed_at=row["processed_at"],
            error_message=row["error_message"],
        )
