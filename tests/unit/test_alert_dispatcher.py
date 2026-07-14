from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.alerts.contracts import AlertRule, ThresholdType
from src.alerts.dispatcher import AlertDispatcher
from src.alerts.repository import AlertRepository
from src.alerts.channels.base import NotificationChannel
from src.core.contract import PriceContract


def make_price(price_cash: str, **overrides) -> PriceContract:
    defaults = dict(
        store_name="kabum",
        search_keyword="rtx 5070",
        product_title="RTX 5070",
        product_url="https://www.kabum.com.br/produto/1",
        price_cash=Decimal(price_cash),
        currency="BRL",
        parser_version="kabum_v2",
        is_available=True,
    )
    defaults.update(overrides)
    return PriceContract(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def mock_repo():
    repo = AsyncMock(spec=AlertRepository)
    repo.get_active_rules.return_value = [
        AlertRule(threshold_type=ThresholdType.ANY_DROP)
    ]
    return repo


@pytest.fixture
def mock_channel():
    channel = AsyncMock(spec=NotificationChannel)
    return channel


@pytest.mark.asyncio
async def test_dispatcher_records_and_sends_on_price_drop(mock_repo, mock_channel):
    dispatcher = AlertDispatcher(alert_repository=mock_repo, channels=[mock_channel])

    # First price: nothing to compare against yet, no event expected.
    await dispatcher.handle_price(make_price("4500.00"))
    mock_repo.save_event.assert_not_called()
    mock_channel.send.assert_not_called()

    # Second, lower price: ANY_DROP rule should fire.
    await dispatcher.handle_price(make_price("4200.00"))
    mock_repo.save_event.assert_called_once()
    mock_channel.send.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_isolates_channel_failures(mock_repo):
    failing_channel = AsyncMock(spec=NotificationChannel)
    failing_channel.send.side_effect = RuntimeError("network down")
    healthy_channel = AsyncMock(spec=NotificationChannel)

    dispatcher = AlertDispatcher(alert_repository=mock_repo, channels=[failing_channel, healthy_channel])

    await dispatcher.handle_price(make_price("4500.00"))
    await dispatcher.handle_price(make_price("4000.00"))

    failing_channel.send.assert_called_once()
    healthy_channel.send.assert_called_once()
