import logging
from typing import List

import aiosqlite

from src.alerts.contracts import AlertEvent, AlertRule
from src.alerts.repository import AlertRepository
from src.core.contract import PriceContract

logger = logging.getLogger(__name__)


class SQLiteAlertRepository(AlertRepository):
    """SQLite implementation of AlertRepository, using the same db file as prices."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize_schema(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_rules (
                    rule_id TEXT PRIMARY KEY,
                    store_name TEXT,
                    search_keyword TEXT,
                    brand TEXT,
                    model TEXT,
                    threshold_type TEXT NOT NULL,
                    threshold_value DECIMAL(10, 2),
                    is_active BOOLEAN NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_history (
                    event_id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    store_name TEXT NOT NULL,
                    search_keyword TEXT NOT NULL,
                    product_title TEXT NOT NULL,
                    product_url TEXT NOT NULL,
                    price_cash DECIMAL(10, 2) NOT NULL,
                    reason TEXT NOT NULL,
                    price_snapshot TEXT NOT NULL,
                    triggered_at TIMESTAMP NOT NULL
                )
                """
            )
            await db.commit()
        logger.info("Alert schema initialized successfully.")

    async def save_rule(self, rule: AlertRule) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO alert_rules (
                    rule_id, store_name, search_keyword, brand, model,
                    threshold_type, threshold_value, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(rule.rule_id),
                    rule.store_name,
                    rule.search_keyword,
                    rule.brand,
                    rule.model,
                    rule.threshold_type.value,
                    float(rule.threshold_value) if rule.threshold_value is not None else None,
                    rule.is_active,
                    rule.created_at.isoformat(),
                ),
            )
            await db.commit()

    async def get_active_rules(self) -> List[AlertRule]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM alert_rules WHERE is_active = 1")
            rows = await cursor.fetchall()

        return [
            AlertRule(
                rule_id=row["rule_id"],
                store_name=row["store_name"],
                search_keyword=row["search_keyword"],
                brand=row["brand"],
                model=row["model"],
                threshold_type=row["threshold_type"],
                threshold_value=row["threshold_value"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def save_event(self, event: AlertEvent) -> None:
        price: PriceContract = event.price
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO alert_history (
                    event_id, rule_id, store_name, search_keyword, product_title,
                    product_url, price_cash, reason, price_snapshot, triggered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.event_id),
                    str(event.rule_id),
                    price.store_name,
                    price.search_keyword,
                    price.product_title,
                    str(price.product_url),
                    float(price.price_cash),
                    event.reason,
                    price.model_dump_json(),
                    event.triggered_at.isoformat(),
                ),
            )
            await db.commit()
        logger.info(
            "Recorded alert event %s for rule %s (%s): %s",
            event.event_id,
            event.rule_id,
            price.store_name,
            event.reason,
        )
