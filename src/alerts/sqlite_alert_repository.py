import logging
from datetime import datetime, timezone
from typing import List

import aiosqlite

from src.alerts.contracts import AlertEvent, AlertRule
from src.alerts.repository import AlertRepository
from src.db.schema import connect
from src.repositories.sqlite_store_repository import get_or_create_store_id

logger = logging.getLogger(__name__)


class SQLiteAlertRepository(AlertRepository):
    """SQLite implementation of AlertRepository, using the same db file as prices."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def save_rule(self, rule: AlertRule) -> None:
        async with connect(self.db_path) as db:
            store_id = rule.store_id
            if store_id is None and rule.store_name:
                store_id = await get_or_create_store_id(db, rule.store_name)
            await db.execute(
                """
                INSERT INTO alert_rules (
                    id, store_id, gpu_model_id, search_keyword,
                    threshold_type, threshold_value, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    store_id = excluded.store_id,
                    gpu_model_id = excluded.gpu_model_id,
                    search_keyword = excluded.search_keyword,
                    threshold_type = excluded.threshold_type,
                    threshold_value = excluded.threshold_value,
                    is_active = excluded.is_active,
                    created_at = excluded.created_at
                """,
                (
                    str(rule.rule_id),
                    store_id,
                    rule.gpu_model_id,
                    rule.search_keyword,
                    rule.threshold_type.value,
                    float(rule.threshold_value) if rule.threshold_value is not None else None,
                    rule.is_active,
                    rule.created_at.isoformat(),
                ),
            )
            await db.commit()

    async def get_active_rules(self) -> List[AlertRule]:
        async with connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT ar.*, s.slug AS store_slug
                FROM alert_rules ar
                LEFT JOIN stores s ON s.id = ar.store_id
                WHERE ar.is_active = 1
                """
            )
            rows = await cursor.fetchall()

        return [
            AlertRule(
                rule_id=row["id"],
                store_id=row["store_id"],
                store_name=row["store_slug"],
                gpu_model_id=row["gpu_model_id"],
                search_keyword=row["search_keyword"],
                threshold_type=row["threshold_type"],
                threshold_value=row["threshold_value"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def save_event(self, event: AlertEvent) -> None:
        async with connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO alert_events (
                    id, alert_rule_id, price_observation_id, reason, triggered_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(event.event_id),
                    str(event.rule_id),
                    event.price_observation_id,
                    event.reason,
                    event.triggered_at.isoformat(),
                ),
            )
            await db.commit()
        logger.info(
            "Recorded alert event %s for rule %s (%s): %s",
            event.event_id,
            event.rule_id,
            event.price.store_name,
            event.reason,
        )
