import json
from decimal import Decimal

import httpx
import pytest
import respx

from src.alerts.channels.telegram import TelegramChannel
from src.alerts.contracts import AlertEvent, AlertRule, ThresholdType
from src.core.contract import PriceContract


def make_event() -> AlertEvent:
    price = PriceContract(
        store_name="kabum",
        search_keyword="rtx 5070",
        product_title="RTX 5070",
        product_url="https://www.kabum.com.br/produto/1",  # type: ignore[arg-type]
        price_cash=Decimal("4200.00"),
        currency="BRL",
        parser_version="kabum_v2",
        is_available=True,
    )
    rule = AlertRule(threshold_type=ThresholdType.ANY_DROP)
    return AlertEvent(rule_id=rule.rule_id, price=price, reason="Price dropped from R$ 4500.00 to R$ 4200.00")


@pytest.mark.asyncio
@respx.mock
async def test_send_posts_formatted_message_to_telegram_api():
    route = respx.post("https://api.telegram.org/bottest-token/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    channel = TelegramChannel(bot_token="test-token", chat_id="12345")

    await channel.send(make_event())

    assert route.called
    payload = json.loads(route.calls.last.request.content)
    assert payload["chat_id"] == "12345"
    assert "RTX 5070" in payload["text"]
    assert "4200.00" in payload["text"]


@pytest.mark.asyncio
@respx.mock
async def test_send_raises_on_http_error_response():
    respx.post("https://api.telegram.org/bottest-token/sendMessage").mock(
        return_value=httpx.Response(400, json={"ok": False, "description": "bad request"})
    )
    channel = TelegramChannel(bot_token="test-token", chat_id="12345")

    with pytest.raises(httpx.HTTPStatusError):
        await channel.send(make_event())
