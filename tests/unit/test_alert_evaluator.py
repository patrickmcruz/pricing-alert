from decimal import Decimal

from src.alerts.contracts import AlertRule, ThresholdType
from src.alerts.evaluator import AlertEvaluator
from src.core.contract import PriceContract


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
        brand="MSI",
        model="rtx 5070",
    )
    defaults.update(overrides)
    return PriceContract(**defaults)


def test_absolute_price_rule_triggers_when_price_at_or_below_threshold():
    rule = AlertRule(threshold_type=ThresholdType.ABSOLUTE_PRICE, threshold_value=Decimal("5000.00"))
    price = make_price(price_cash=Decimal("4500.00"))

    events = AlertEvaluator.evaluate(price, [rule])

    assert len(events) == 1
    assert events[0].rule_id == rule.rule_id
    assert "4500.00" in events[0].reason


def test_absolute_price_rule_does_not_trigger_above_threshold():
    rule = AlertRule(threshold_type=ThresholdType.ABSOLUTE_PRICE, threshold_value=Decimal("4000.00"))
    price = make_price(price_cash=Decimal("4500.00"))

    assert AlertEvaluator.evaluate(price, [rule]) == []


def test_any_drop_rule_requires_previous_price_lower_than_current():
    rule = AlertRule(threshold_type=ThresholdType.ANY_DROP)
    price = make_price(price_cash=Decimal("4500.00"))

    assert AlertEvaluator.evaluate(price, [rule], previous_price=None) == []
    assert AlertEvaluator.evaluate(price, [rule], previous_price=Decimal("4500.00")) == []
    assert AlertEvaluator.evaluate(price, [rule], previous_price=Decimal("4600.00")) != []


def test_percent_drop_rule_triggers_only_past_threshold():
    rule = AlertRule(threshold_type=ThresholdType.PERCENT_DROP, threshold_value=Decimal("10"))
    price = make_price(price_cash=Decimal("4500.00"))

    # 4500 vs 4600 is a ~2.2% drop - below the 10% threshold.
    assert AlertEvaluator.evaluate(price, [rule], previous_price=Decimal("4600.00")) == []

    # 4500 vs 5200 is a ~13.5% drop - past the 10% threshold.
    events = AlertEvaluator.evaluate(price, [rule], previous_price=Decimal("5200.00"))
    assert len(events) == 1


def test_inactive_rule_never_triggers():
    rule = AlertRule(threshold_type=ThresholdType.ABSOLUTE_PRICE, threshold_value=Decimal("9999"), is_active=False)
    price = make_price(price_cash=Decimal("100.00"))

    assert AlertEvaluator.evaluate(price, [rule]) == []


def test_rule_filters_by_store_and_keyword():
    rule = AlertRule(
        store_name="terabyte",
        search_keyword="rtx 5070",
        threshold_type=ThresholdType.ABSOLUTE_PRICE,
        threshold_value=Decimal("9999"),
    )
    price = make_price(store_name="kabum")  # different store

    assert AlertEvaluator.evaluate(price, [rule]) == []


def test_unavailable_price_never_triggers():
    rule = AlertRule(threshold_type=ThresholdType.ABSOLUTE_PRICE, threshold_value=Decimal("9999"))
    price = make_price(price_cash=Decimal("0"), is_available=False)

    assert AlertEvaluator.evaluate(price, [rule]) == []
