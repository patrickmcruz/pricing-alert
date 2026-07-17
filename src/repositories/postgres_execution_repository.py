import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from src.core.execution import RunStatus, ScraperRunRecord, SkuRunRecord, SkuRunStatus
from src.db.schema import affected_rows, connect
from src.repositories.execution_repository import ExecutionRepository
from src.repositories.postgres_store_repository import get_or_create_store_id

logger = logging.getLogger(__name__)


class PostgresExecutionRepository(ExecutionRepository):
    """PostgreSQL implementation of ExecutionRepository, using the same database as prices."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    async def start_run(self, store_name: str) -> UUID:
        run_id = uuid4()
        started_at = datetime.now(timezone.utc)
        async with connect(self.dsn) as db:
            async with db.transaction():
                store_id = await get_or_create_store_id(db, store_name)
                await db.execute(
                    "INSERT INTO scraper_runs (id, loja_id, status, started_at) VALUES ($1, $2, $3, $4)",
                    str(run_id), store_id, RunStatus.RUNNING.value, started_at,
                )
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
        async with connect(self.dsn) as db:
            await db.execute(
                """
                UPDATE scraper_runs
                SET status = $1, finished_at = $2, listings_total = $3, listings_succeeded = $4,
                    listings_failed = $5, error_message = $6
                WHERE id = $7
                """,
                status.value, finished_at, listings_total, listings_succeeded,
                listings_failed, error_message, str(run_id),
            )

    async def get_latest_runs(self) -> List[ScraperRunRecord]:
        async with connect(self.dsn) as db:
            rows = await db.fetch(
                """
                SELECT r.*, l.slug AS store_slug FROM scraper_runs r
                JOIN loja l ON l.id = r.loja_id
                INNER JOIN (
                    SELECT loja_id, MAX(started_at) AS max_started
                    FROM scraper_runs
                    GROUP BY loja_id
                ) latest
                ON r.loja_id = latest.loja_id AND r.started_at = latest.max_started
                ORDER BY l.slug
                """
            )
        return [self._row_to_record(row) for row in rows]

    async def get_run_history(self, limit: int = 50) -> List[ScraperRunRecord]:
        async with connect(self.dsn) as db:
            rows = await db.fetch(
                """
                SELECT r.*, l.slug AS store_slug FROM scraper_runs r
                JOIN loja l ON l.id = r.loja_id
                ORDER BY r.started_at DESC LIMIT $1
                """,
                limit,
            )
        return [self._row_to_record(row) for row in rows]

    async def fail_stale_running_runs(self, error_message: str) -> int:
        finished_at = datetime.now(timezone.utc)
        async with connect(self.dsn) as db:
            status = await db.execute(
                """
                UPDATE scraper_runs
                SET status = $1, finished_at = $2, error_message = $3
                WHERE status = $4
                """,
                RunStatus.FAILED.value, finished_at, error_message, RunStatus.RUNNING.value,
            )
            count = affected_rows(status)
        if count:
            logger.warning("Marked %d orphaned 'running' scraper run(s) as failed on startup.", count)
        return count

    async def start_sku_run(
        self, run_id: UUID, store_name: str, product_url: str, product_title: str
    ) -> UUID:
        sku_run_id = uuid4()
        started_at = datetime.now(timezone.utc)
        async with connect(self.dsn) as db:
            row = await db.fetchrow("SELECT id FROM anuncio WHERE product_url = $1", product_url)
            anuncio_id = row["id"] if row else None
            await db.execute(
                """
                INSERT INTO listing_runs
                    (id, scraper_run_id, anuncio_id, product_url, product_title, status, started_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                str(sku_run_id), str(run_id), anuncio_id, product_url, product_title,
                SkuRunStatus.RUNNING.value, started_at,
            )
        return sku_run_id

    async def finish_sku_run(
        self, sku_run_id: UUID, status: SkuRunStatus, error_message: Optional[str] = None
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        async with connect(self.dsn) as db:
            await db.execute(
                "UPDATE listing_runs SET status = $1, finished_at = $2, error_message = $3 WHERE id = $4",
                status.value, finished_at, error_message, str(sku_run_id),
            )

    async def get_current_sku_run(self, run_id: UUID) -> Optional[SkuRunRecord]:
        async with connect(self.dsn) as db:
            row = await db.fetchrow(
                """
                SELECT lr.*, l.slug AS store_slug
                FROM listing_runs lr
                JOIN scraper_runs sr ON sr.id = lr.scraper_run_id
                JOIN loja l ON l.id = sr.loja_id
                WHERE lr.scraper_run_id = $1 AND lr.status = $2
                ORDER BY lr.started_at DESC LIMIT 1
                """,
                str(run_id), SkuRunStatus.RUNNING.value,
            )
        return self._row_to_sku_record(row, run_id) if row else None

    async def get_sku_run_counts(self, run_id: UUID) -> Dict[SkuRunStatus, int]:
        async with connect(self.dsn) as db:
            rows = await db.fetch(
                "SELECT status, COUNT(*) AS n FROM listing_runs WHERE scraper_run_id = $1 GROUP BY status",
                str(run_id),
            )
        return {SkuRunStatus(row["status"]): row["n"] for row in rows}

    async def fail_stale_running_sku_runs(self, error_message: str) -> int:
        finished_at = datetime.now(timezone.utc)
        async with connect(self.dsn) as db:
            status = await db.execute(
                """
                UPDATE listing_runs
                SET status = $1, finished_at = $2, error_message = $3
                WHERE status = $4
                """,
                SkuRunStatus.FAILED.value, finished_at, error_message, SkuRunStatus.RUNNING.value,
            )
            count = affected_rows(status)
        if count:
            logger.warning("Marked %d orphaned 'running' sku run(s) as failed on startup.", count)
        return count

    @staticmethod
    def _row_to_sku_record(row, run_id: UUID) -> SkuRunRecord:
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
    def _row_to_record(row) -> ScraperRunRecord:
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
