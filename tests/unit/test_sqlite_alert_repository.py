from decimal import Decimal

import aiosqlite
import pytest

from src.alerts.contracts import AlertEvent, AlertRule, ThresholdType
from src.alerts.sqlite_alert_repository import SQLiteAlertRepository
from src.core.contract import PriceContract


@pytest.fixture
async def repo(tmp_path):
    db_path = str(tmp_path / "alerts_test.db")
    repository = SQLiteAlertRepository(db_path)
    await repository.initialize_schema()
    yield repository


def make_price(**overrides) -> PriceContract:
    defaults = dict(
        store_name="kabum",
        search_keyword="rtx 5070",
        product_title="RTX 5070",
        product_url="https://www.kabum.com.br/produto/1",
        price_cash=Decimal("4500.00"),
        currency="BRL",
        parser_version="kabum_v2",
        is_available=True,
    )
    defaults.update(overrides)
    return PriceContract(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_save_and_get_active_rules_roundtrip(repo):
    rule = AlertRule(
        store_name="kabum",
        search_keyword="rtx 5070",
        threshold_type=ThresholdType.ABSOLUTE_PRICE,
        threshold_value=Decimal("5000.00"),
    )

    await repo.save_rule(rule)
    rules = await repo.get_active_rules()

    assert len(rules) == 1
    assert rules[0].rule_id == rule.rule_id
    assert rules[0].store_name == "kabum"
    assert rules[0].threshold_type == ThresholdType.ABSOLUTE_PRICE
    assert rules[0].threshold_value == Decimal("5000.00")


@pytest.mark.asyncio
async def test_get_active_rules_excludes_inactive(repo):
    active_rule = AlertRule(threshold_type=ThresholdType.ANY_DROP, is_active=True)
    inactive_rule = AlertRule(threshold_type=ThresholdType.ANY_DROP, is_active=False)
    await repo.save_rule(active_rule)
    await repo.save_rule(inactive_rule)

    rules = await repo.get_active_rules()

    assert len(rules) == 1
    assert rules[0].rule_id == active_rule.rule_id


@pytest.mark.asyncio
async def test_save_rule_upserts_by_rule_id(repo):
    rule = AlertRule(threshold_type=ThresholdType.ABSOLUTE_PRICE, threshold_value=Decimal("5000.00"))
    await repo.save_rule(rule)

    updated = rule.model_copy(update={"threshold_value": Decimal("4000.00")})
    await repo.save_rule(updated)

    rules = await repo.get_active_rules()
    assert len(rules) == 1
    assert rules[0].threshold_value == Decimal("4000.00")


@pytest.mark.asyncio
async def test_save_event_persists_without_error(repo):
    rule = AlertRule(threshold_type=ThresholdType.ANY_DROP)
    price = make_price()
    event = AlertEvent(rule_id=rule.rule_id, price=price, reason="test drop")

    await repo.save_event(event)

    async with aiosqlite.connect(repo.db_path) as db:
        cursor = await db.execute("SELECT event_id, reason, price_cash FROM alert_history")
        row = await cursor.fetchone()

    assert row is not None
    assert row[0] == str(event.event_id)
    assert row[1] == "test drop"
    assert row[2] == 4500.00
