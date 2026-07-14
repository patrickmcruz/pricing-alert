import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import aiosqlite

from src.core.execution import RunStatus, ScraperRunRecord, SkuRunRecord, SkuRunStatus
from src.repositories.execution_repository import ExecutionRepository

logger = logging.getLogger(__name__)


class SQLiteExecutionRepository(ExecutionRepository):
    """SQLite implementation of ExecutionRepository, using the same db file as prices."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize_schema(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS scraper_runs (
                    run_id TEXT PRIMARY KEY,
                    store_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    finished_at TIMESTAMP,
                    skus_total INTEGER NOT NULL DEFAULT 0,
                    skus_succeeded INTEGER NOT NULL DEFAULT 0,
                    skus_failed INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_scraper_runs_store ON scraper_runs(store_name)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_scraper_runs_started_at ON scraper_runs(started_at)"
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sku_runs (
                    sku_run_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES scraper_runs(run_id),
                    store_name TEXT NOT NULL,
                    product_url TEXT NOT NULL,
                    product_title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    finished_at TIMESTAMP,
                    error_message TEXT
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sku_runs_run_id ON sku_runs(run_id)"
            )
            await db.commit()
        logger.info("Execution schema initialized successfully.")

    async def start_run(self, store_name: str) -> UUID:
        run_id = uuid4()
        started_at = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO scraper_runs (run_id, store_name, status, started_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(run_id), store_name, RunStatus.RUNNING.value, started_at.isoformat()),
            )
            await db.commit()
        return run_id

    async def finish_run(
        self,
        run_id: UUID,
        status: RunStatus,
        skus_total: int,
        skus_succeeded: int,
        skus_failed: int,
        error_message: Optional[str] = None,
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE scraper_runs
                SET status = ?, finished_at = ?, skus_total = ?, skus_succeeded = ?,
                    skus_failed = ?, error_message = ?
                WHERE run_id = ?
                """,
                (
                    status.value,
                    finished_at.isoformat(),
                    skus_total,
                    skus_succeeded,
                    skus_failed,
                    error_message,
                    str(run_id),
                ),
            )
            await db.commit()

    async def get_latest_runs(self) -> List[ScraperRunRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT r.* FROM scraper_runs r
                INNER JOIN (
                    SELECT store_name, MAX(started_at) AS max_started
                    FROM scraper_runs
                    GROUP BY store_name
                ) latest
                ON r.store_name = latest.store_name AND r.started_at = latest.max_started
                ORDER BY r.store_name
                """
            )
            rows = await cursor.fetchall()
        return [self._row_to_record(row) for row in rows]

    async def get_run_history(self, limit: int = 50) -> List[ScraperRunRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM scraper_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [self._row_to_record(row) for row in rows]

    async def fail_stale_running_runs(self, error_message: str) -> int:
        finished_at = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
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
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO sku_runs
                    (sku_run_id, run_id, store_name, product_url, product_title, status, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(sku_run_id),
                    str(run_id),
                    store_name,
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
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE sku_runs
                SET status = ?, finished_at = ?, error_message = ?
                WHERE sku_run_id = ?
                """,
                (status.value, finished_at.isoformat(), error_message, str(sku_run_id)),
            )
            await db.commit()

    async def get_current_sku_run(self, run_id: UUID) -> Optional[SkuRunRecord]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM sku_runs WHERE run_id = ? AND status = ? ORDER BY started_at DESC LIMIT 1",
                (str(run_id), SkuRunStatus.RUNNING.value),
            )
            row = await cursor.fetchone()
        return self._row_to_sku_record(row) if row else None

    async def get_sku_run_counts(self, run_id: UUID) -> Dict[SkuRunStatus, int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT status, COUNT(*) FROM sku_runs WHERE run_id = ? GROUP BY status",
                (str(run_id),),
            )
            rows = await cursor.fetchall()
        return {SkuRunStatus(status): count for status, count in rows}

    async def fail_stale_running_sku_runs(self, error_message: str) -> int:
        finished_at = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE sku_runs
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
    def _row_to_sku_record(row: aiosqlite.Row) -> SkuRunRecord:
        return SkuRunRecord(
            sku_run_id=row["sku_run_id"],
            run_id=row["run_id"],
            store_name=row["store_name"],
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
            run_id=row["run_id"],
            store_name=row["store_name"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            skus_total=row["skus_total"],
            skus_succeeded=row["skus_succeeded"],
            skus_failed=row["skus_failed"],
            error_message=row["error_message"],
        )
