import logging
from typing import List

from src.alerts.contracts import AlertEvent, AlertRule
from src.alerts.repository import AlertRepository
from src.db.schema import connect
from src.repositories.postgres_store_repository import get_or_create_store_id

logger = logging.getLogger(__name__)


class PostgresAlertRepository(AlertRepository):
    """PostgreSQL implementation of AlertRepository, using the same database as prices."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    async def save_rule(self, rule: AlertRule) -> None:
        async with connect(self.dsn) as db:
            async with db.transaction():
                store_id = rule.store_id
                if store_id is None and rule.store_name:
                    store_id = await get_or_create_store_id(db, rule.store_name)
                await db.execute(
                    """
                    INSERT INTO alert_rules (
                        id, store_id, product_id, search_keyword,
                        threshold_type, threshold_value, is_active, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (id) DO UPDATE SET
                        store_id = EXCLUDED.store_id,
                        product_id = EXCLUDED.product_id,
                        search_keyword = EXCLUDED.search_keyword,
                        threshold_type = EXCLUDED.threshold_type,
                        threshold_value = EXCLUDED.threshold_value,
                        is_active = EXCLUDED.is_active,
                        created_at = EXCLUDED.created_at
                    """,
                    str(rule.rule_id),
                    store_id,
                    rule.produto_id,
                    rule.search_keyword,
                    rule.threshold_type.value,
                    rule.threshold_value,
                    rule.is_active,
                    rule.created_at,
                )

    async def get_active_rules(self) -> List[AlertRule]:
        async with connect(self.dsn) as db:
            rows = await db.fetch(
                """
                SELECT ar.*, l.slug AS store_slug
                FROM alert_rules ar
                LEFT JOIN stores l ON l.id = ar.store_id
                WHERE ar.is_active = true
                """
            )

        return [
            AlertRule(
                rule_id=row["id"],
                store_id=str(row["store_id"]) if row["store_id"] else None,
                store_name=row["store_slug"],
                produto_id=str(row["product_id"]) if row["product_id"] else None,
                search_keyword=row["search_keyword"],
                threshold_type=row["threshold_type"],
                threshold_value=row["threshold_value"],
                is_active=row["is_active"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def save_event(self, event: AlertEvent) -> None:
        async with connect(self.dsn) as db:
            await db.execute(
                """
                INSERT INTO alert_events (
                    alert_rule_id, price_observation_id, reason, triggered_at
                ) VALUES ($1, $2, $3, $4)
                """,
                str(event.rule_id),
                event.coleta_preco_id,
                event.reason,
                event.triggered_at,
            )
        logger.info(
            "Recorded alert event for rule %s (%s): %s",
            event.rule_id,
            event.price.store_name,
            event.reason,
        )
