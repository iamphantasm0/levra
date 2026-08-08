from decimal import Decimal

from levra.engine.liquidation import project_liquidation
from levra.models import Direction


def test_long_liquidation_sits_below_entry():
    liq = project_liquidation(
        entry=Decimal("3200"),
        stop=Decimal("3100"),
        leverage=Decimal("2"),
        maintenance_margin_rate=Decimal("0.005"),
        direction=Direction.LONG,
    )
    assert liq.price == Decimal("1616.00")


def test_short_liquidation_sits_above_entry():
    liq = project_liquidation(
        entry=Decimal("3200"),
        stop=Decimal("3300"),
        leverage=Decimal("2"),
        maintenance_margin_rate=Decimal("0.005"),
        direction=Direction.SHORT,
    )
    assert liq.price == Decimal("4784.00")


def test_buffer_ratio_compares_liquidation_distance_to_stop_distance():
    liq = project_liquidation(
        entry=Decimal("3200"),
        stop=Decimal("3100"),
        leverage=Decimal("2"),
        maintenance_margin_rate=Decimal("0.005"),
        direction=Direction.LONG,
    )
    assert liq.buffer_ratio == Decimal("15.84")


def test_higher_leverage_moves_liquidation_closer():
    low = project_liquidation(
        Decimal("3200"), Decimal("3100"), Decimal("2"), Decimal("0.005"), Direction.LONG
    )
    high = project_liquidation(
        Decimal("3200"), Decimal("3100"), Decimal("8"), Decimal("0.005"), Direction.LONG
    )
    assert high.price > low.price
    assert high.buffer_ratio < low.buffer_ratio
