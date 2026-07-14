import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import aiosqlite

from src.core.execution import RunStatus, ScraperRunRecord, SkuRunRecord, SkuRunStatus
from src.db.schema import connect
from src.repositories.execution_repository import ExecutionRepository
from src.repositories.sqlite_store_repository import get_or_create_store_id

logger = logging.getLogger(__name__)


class SQLiteExecutionRepository(ExecutionRepository):
    """SQLite implementation of ExecutionRepository, using the same db file as prices."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def start_run(self, store_name: str) -> UUID:
        run_id = uuid4()
        started_at = datetime.now(timezone.utc)
        async with connect(self.db_path) as db:
            store_id = await get_or_create_store_id(db, store_name)
            await db.execute(
                """
                INSERT INTO scraper_runs (id, store_id, status, started_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(run_id), store_id, RunStatus.RUNNING.value, started_at.isoformat()),
            )
            await db.commit()
        return run_id

    async def finish_run(
        self,
        run_id: UUID,
        status: RunStatus,
        listings_total: int,
        listings_succeeded: int,
        listings_failed: int,
        error_message: Optional[str] = None,
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        async with connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE scraper_runs
                SET status = ?, finished_at = ?, listings_total = ?, listings_succeeded = ?,
                    listings_failed = ?, error_message = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    finished_at.isoformat(),
                    listings_total,
                    listings_succeeded,
                    listings_failed,
                    error_message,
                    str(run_id),
                ),
            )
            await db.commit()

    async def get_latest_runs(self) -> List[ScraperRunRecord]:
        async with connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT r.*, s.slug AS store_slug FROM scraper_runs r
                JOIN stores s ON s.id = r.store_id
                INNER JOIN (
                    SELECT store_id, MAX(started_at) AS max_started
                    FROM scraper_runs
                    GROUP BY store_id
                ) latest
                ON r.store_id = latest.store_id AND r.started_at = latest.max_started
                ORDER BY s.slug
                """
            )
            rows = await cursor.fetchall()
        return [self._row_to_record(row) for row in rows]

    async def get_run_history(self, limit: int = 50) -> List[ScraperRunRecord]:
        async with connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT r.*, s.slug AS store_slug FROM scraper_runs r
                JOIN stores s ON s.id = r.store_id
                ORDER BY r.started_at DESC LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
        return [self._row_to_record(row) for row in rows]

    async def fail_stale_running_runs(self, error_message: str) -> int:
        finished_at = datetime.now(timezone.utc).isoformat()
        async with connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE scraper_runs
                SET status = ?, finished_at = ?, error_message = ?
                WHERE status = ?
                """,
                (RunStatus.FAILED.value, finished_at, error_message, RunStatus.RUNNING.value),
            )
            await db.commit()
            count = cursor.rowcount
        if count:
            logger.warning("Marked %d orphaned 'running' scraper run(s) as failed on startup.", count)
        return count

    async def start_sku_run(
        self, run_id: UUID, store_name: str, product_url: str, product_title: str
    ) -> UUID:
        sku_run_id = uuid4()
        started_at = datetime.now(timezone.utc)
        async with connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id FROM store_listings WHERE product_url = ?", (product_url,)
            )
            row = await cursor.fetchone()
            store_listing_id = row[0] if row else None
            await db.execute(
                """
                INSERT INTO listing_runs
                    (id, scraper_run_id, store_listing_id, product_url, product_title, status, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(sku_run_id),
                    str(run_id),
                    store_listing_id,
                    product_url,
                    product_title,
                    SkuRunStatus.RUNNING.value,
                    started_at.isoformat(),
                ),
            )
            await db.commit()
        return sku_run_id

    async def finish_sku_run(
        self, sku_run_id: UUID, status: SkuRunStatus, error_message: Optional[str] = None
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        async with connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE listing_runs
                SET status = ?, finished_at = ?, error_message = ?
                WHERE id = ?
                """,
                (status.value, finished_at.isoformat(), error_message, str(sku_run_id)),
            )
            await db.commit()

    async def get_current_sku_run(self, run_id: UUID) -> Optional[SkuRunRecord]:
        async with connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT lr.*, s.slug AS store_slug
                FROM listing_runs lr
                JOIN scraper_runs sr ON sr.id = lr.scraper_run_id
                JOIN stores s ON s.id = sr.store_id
                WHERE lr.scraper_run_id = ? AND lr.status = ?
                ORDER BY lr.started_at DESC LIMIT 1
                """,
                (str(run_id), SkuRunStatus.RUNNING.value),
            )
            row = await cursor.fetchone()
        return self._row_to_sku_record(row, run_id) if row else None

    async def get_sku_run_counts(self, run_id: UUID) -> Dict[SkuRunStatus, int]:
        async with connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT status, COUNT(*) FROM listing_runs WHERE scraper_run_id = ? GROUP BY status",
                (str(run_id),),
            )
            rows = await cursor.fetchall()
        return {SkuRunStatus(status): count for status, count in rows}

    async def fail_stale_running_sku_runs(self, error_message: str) -> int:
        finished_at = datetime.now(timezone.utc).isoformat()
        async with connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE listing_runs
                SET status = ?, finished_at = ?, error_message = ?
                WHERE status = ?
                """,
                (SkuRunStatus.FAILED.value, finished_at, error_message, SkuRunStatus.RUNNING.value),
            )
            await db.commit()
            count = cursor.rowcount
        if count:
            logger.warning("Marked %d orphaned 'running' sku run(s) as failed on startup.", count)
        return count

    @staticmethod
    def _row_to_sku_record(row: aiosqlite.Row, run_id: UUID) -> SkuRunRecord:
        return SkuRunRecord(
            sku_run_id=row["id"],
            run_id=run_id,
            store_name=row["store_slug"],
            product_url=row["product_url"],
            product_title=row["product_title"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            error_message=row["error_message"],
        )

    @staticmethod
    def _row_to_record(row: aiosqlite.Row) -> ScraperRunRecord:
        return ScraperRunRecord(
            run_id=row["id"],
            store_name=row["store_slug"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            listings_total=row["listings_total"],
            listings_succeeded=row["listings_succeeded"],
            listings_failed=row["listings_failed"],
            error_message=row["error_message"],
        )
