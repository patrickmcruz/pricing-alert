import logging

import httpx

from src.alerts.channels.base import NotificationChannel
from src.alerts.contracts import AlertEvent

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramChannel(NotificationChannel):
    """Delivers alert events as messages via a Telegram bot."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, event: AlertEvent) -> None:
        url = f"{TELEGRAM_API_BASE}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": self._format_message(event),
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

    @staticmethod
    def _format_message(event: AlertEvent) -> str:
        price = event.price
        return (
            f"🔔 *Price Alert - {price.store_name}*\n"
            f"{price.product_title}\n\n"
            f"💰 R$ {price.price_cash}\n"
            f"{event.reason}\n\n"
            f"{price.product_url}"
        )
