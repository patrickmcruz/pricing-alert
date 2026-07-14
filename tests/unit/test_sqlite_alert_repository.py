from decimal import Decimal

import aiosqlite
import pytest

from src.alerts.contracts import AlertEvent, AlertRule, ThresholdType
from src.alerts.sqlite_alert_repository import SQLiteAlertRepository
from src.core.contract import PriceContract
from src.db.schema import initialize_schema as initialize_db_schema
from src.repositories.sqlite_repository import SQLitePriceRepository

from tests.conftest import make_gpu_model_id


@pytest.fixture
async def repo(tmp_path):
    db_path = str(tmp_path / "alerts_test.db")
    await initialize_db_schema(db_path)
    repository = SQLiteAlertRepository(db_path)
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


async def _seed_price_observation(db_path: str, price: PriceContract) -> str:
    """
    Persists a real store_listings row + price_observations row for `price`
    and returns the generated price_observations.id - alert_events.price_observation_id
    is FK-enforced, so tests need a real id rather than a placeholder string.
    """
    from src.core.contract import ProductSKU

    gpu_model_id = await make_gpu_model_id(db_path)
    price_repo = SQLitePriceRepository(db_path)
    await price_repo.save_skus(
        [
            ProductSKU(
                product_url=str(price.product_url),
                store_name=price.store_name,
                search_keyword=price.search_keyword,
                gpu_model_id=gpu_model_id,
                product_title=price.product_title,
            )
        ]
    )
    observation_ids = await price_repo.save_prices([price])
    return observation_ids[0]


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
    await repo.save_rule(rule)
    price = make_price()
    observation_id = await _seed_price_observation(repo.db_path, price)
    event = AlertEvent(
        rule_id=rule.rule_id, price_observation_id=observation_id, price=price, reason="test drop"
    )

    await repo.save_event(event)

    async with aiosqlite.connect(repo.db_path) as db:
        cursor = await db.execute(
            """
            SELECT ae.id, ae.reason, po.price_cash
            FROM alert_events ae
            JOIN price_observations po ON po.id = ae.price_observation_id
            """
        )
        row = await cursor.fetchone()

    assert row is not None
    assert row[0] == str(event.event_id)
    assert row[1] == "test drop"
    assert row[2] == 4500.00
