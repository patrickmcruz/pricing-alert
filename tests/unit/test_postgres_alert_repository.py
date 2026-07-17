from decimal import Decimal

import pytest

from src.alerts.contracts import AlertEvent, AlertRule, ThresholdType
from src.alerts.postgres_alert_repository import PostgresAlertRepository
from src.core.contract import PriceContract
from src.db.schema import connect
from src.repositories.postgres_repository import PostgresPriceRepository

from tests.conftest import make_produto_id


@pytest.fixture
async def repo(db_dsn):
    return PostgresAlertRepository(db_dsn)


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


async def _seed_price_observation(dsn: str, price: PriceContract) -> str:
    """
    Persists a real anuncio row + coleta_preco row for `price` and returns the
    generated coleta_preco.id - alert_events.coleta_preco_id is FK-enforced,
    so tests need a real id rather than a placeholder string.
    """
    from src.core.contract import ProductSKU

    produto_id = await make_produto_id(dsn)
    price_repo = PostgresPriceRepository(dsn)
    await price_repo.save_skus(
        [
            ProductSKU(
                product_url=str(price.product_url),
                store_name=price.store_name,
                search_keyword=price.search_keyword,
                produto_id=produto_id,
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
async def test_save_event_persists_without_error(repo, db_dsn):
    rule = AlertRule(threshold_type=ThresholdType.ANY_DROP)
    await repo.save_rule(rule)
    price = make_price()
    observation_id = await _seed_price_observation(db_dsn, price)
    event = AlertEvent(
        rule_id=rule.rule_id, coleta_preco_id=observation_id, price=price, reason="test drop"
    )

    await repo.save_event(event)

    async with connect(db_dsn) as db:
        row = await db.fetchrow(
            """
            SELECT ae.id, ae.reason, cp.price_cash
            FROM alert_events ae
            JOIN coleta_preco cp ON cp.id = ae.coleta_preco_id
            """
        )

    assert row is not None
    assert row["reason"] == "test drop"
    assert row["price_cash"] == Decimal("4500.00")
