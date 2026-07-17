from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from src.alerts.contracts import AlertEvent, AlertRule, ThresholdType
from src.core.contract import PriceContract


class AlertEvaluator:
    """
    Pure rule-matching logic: no I/O, deterministic, fixture-testable.
    `previous_price` (the last known cash price for this store/keyword) is
    supplied by the caller since PERCENT_DROP/ANY_DROP need history that the
    evaluator itself must not fetch.
    """

    @staticmethod
    def evaluate(
        price: PriceContract,
        rules: List[AlertRule],
        previous_price: Optional[Decimal] = None,
        coleta_preco_id: str = "",
    ) -> List[AlertEvent]:
        """
        coleta_preco_id is threaded onto every AlertEvent produced, so it
        can be persisted as the FK into coleta_preco (see
        src/alerts/repository.py). Defaults to "" to keep this call ergonomic
        for callers/tests that don't care about the FK; real callers
        (AlertDispatcher.handle_price) always pass the real id.
        """
        if not price.is_available:
            return []

        events: List[AlertEvent] = []
        for rule in rules:
            if not rule.is_active or not rule.matches(price):
                continue

            reason = AlertEvaluator._check_threshold(rule, price, previous_price)
            if reason:
                events.append(
                    AlertEvent(
                        rule_id=rule.rule_id,
                        coleta_preco_id=coleta_preco_id,
                        price=price,
                        reason=reason,
                    )
                )

        return events

    @staticmethod
    def _check_threshold(
        rule: AlertRule, price: PriceContract, previous_price: Optional[Decimal]
    ) -> Optional[str]:
        if rule.threshold_type == ThresholdType.ABSOLUTE_PRICE:
            if rule.threshold_value is not None and price.price_cash <= rule.threshold_value:
                return f"Price R$ {price.price_cash} reached target of R$ {rule.threshold_value}"
            return None

        if previous_price is None or previous_price <= 0 or price.price_cash >= previous_price:
            return None

        if rule.threshold_type == ThresholdType.ANY_DROP:
            return f"Price dropped from R$ {previous_price} to R$ {price.price_cash}"

        if rule.threshold_type == ThresholdType.PERCENT_DROP and rule.threshold_value is not None:
            drop_pct = (previous_price - price.price_cash) / previous_price * 100
            if drop_pct >= rule.threshold_value:
                return f"Price dropped {drop_pct:.1f}% (>= {rule.threshold_value}%): R$ {previous_price} -> R$ {price.price_cash}"

        return None
