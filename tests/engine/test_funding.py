from decimal import Decimal

from levra.engine.funding import project_funding
from levra.models import Direction


def test_interval_count_covers_the_horizon():
    p = project_funding(
        Decimal("10000"), Decimal("0.0001"), 8, horizon_days=30, direction=Direction.LONG
    )
    assert p.intervals == 90  # 30 days x 24h / 8h


def test_long_pays_when_funding_is_positive():
    p = project_funding(
        Decimal("10000"), Decimal("0.0001"), 8, horizon_days=30, direction=Direction.LONG
    )
    assert p.cost == Decimal("90.00")


def test_short_earns_when_funding_is_positive():
    p = project_funding(
        Decimal("10000"), Decimal("0.0001"), 8, horizon_days=30, direction=Direction.SHORT
    )
    assert p.cost == Decimal("-90.00")


def test_long_earns_when_funding_is_negative():
    p = project_funding(
        Decimal("10000"), Decimal("-0.0001"), 8, horizon_days=30, direction=Direction.LONG
    )
    assert p.cost == Decimal("-90.00")


def test_partial_final_interval_is_not_counted():
    p = project_funding(
        Decimal("10000"), Decimal("0.0001"), 8, horizon_days=1, direction=Direction.LONG
    )
    assert p.intervals == 3
