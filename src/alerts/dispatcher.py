import logging
from decimal import Decimal
from typing import Dict, List, Tuple

from src.alerts.channels.base import NotificationChannel
from src.alerts.evaluator import AlertEvaluator
from src.alerts.repository import AlertRepository
from src.core.contract import PriceContract

logger = logging.getLogger(__name__)


class AlertDispatcher:
    """
    Owns rule evaluation + notification delivery for newly-saved prices.
    Isolated from PriceEngine behind a plain callback (see PriceEngine.on_price_saved) -
    PriceEngine never imports this module, keeping orchestration decoupled from alerting.
    """

    def __init__(self, alert_repository: AlertRepository, channels: List[NotificationChannel]):
        self.alert_repository = alert_repository
        self.channels = channels
        # In-process last-seen-price cache for PERCENT_DROP/ANY_DROP rules, keyed by
        # (store_name, search_keyword). Resets on restart - a single-process, single-user
        # app doesn't need durable trend state, and the first price after a restart will
        # simply not have a "previous_price" to compare against yet.
        self._last_seen_prices: Dict[Tuple[str, str], Decimal] = {}

    async def handle_price(self, price: PriceContract, price_observation_id: str) -> None:
        key = (price.store_name, price.search_keyword)
        previous_price = self._last_seen_prices.get(key)

        rules = await self.alert_repository.get_active_rules()
        events = AlertEvaluator.evaluate(price, rules, previous_price, price_observation_id)

        if price.is_available:
            self._last_seen_prices[key] = price.price_cash

        for event in events:
            await self.alert_repository.save_event(event)
            for channel in self.channels:
                try:
                    await channel.send(event)
                except Exception as e:
                    logger.error(
                        "Notification channel %s failed for event %s: %s",
                        channel.__class__.__name__,
                        event.event_id,
                        e,
                        exc_info=True,
                    )
