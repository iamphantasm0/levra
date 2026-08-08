from decimal import Decimal

import pytest

from levra.engine.entry import build_entry_zone
from levra.errors import InvalidZone
from levra.models import Direction


def test_long_zone_sits_below_mark_and_above_stop():
    zone = build_entry_zone(Decimal("3200"), Decimal("3100"), Direction.LONG)
    assert zone.low == Decimal("3175.00")
    assert zone.high == Decimal("3200.00")


def test_long_sizing_edge_is_the_edge_furthest_from_the_stop():
    zone = build_entry_zone(Decimal("3200"), Decimal("3100"), Direction.LONG)
    assert zone.sizing_edge == zone.high == Decimal("3200.00")


def test_short_zone_sits_above_mark_and_below_stop():
    zone = build_entry_zone(Decimal("3200"), Decimal("3300"), Direction.SHORT)
    assert zone.low == Decimal("3200.00")
    assert zone.high == Decimal("3225.00")


def test_short_sizing_edge_is_the_edge_furthest_from_the_stop():
    zone = build_entry_zone(Decimal("3200"), Decimal("3300"), Direction.SHORT)
    assert zone.sizing_edge == zone.low == Decimal("3200.00")


def test_zone_never_crosses_the_stop():
    zone = build_entry_zone(Decimal("3200"), Decimal("3100"), Direction.LONG)
    assert zone.low > Decimal("3100")


def test_rejects_long_whose_stop_is_above_mark():
    with pytest.raises(InvalidZone):
        build_entry_zone(Decimal("3100"), Decimal("3200"), Direction.LONG)


def test_rejects_short_whose_stop_is_below_mark():
    with pytest.raises(InvalidZone):
        build_entry_zone(Decimal("3200"), Decimal("3100"), Direction.SHORT)


def test_rejects_zero_distance():
    with pytest.raises(InvalidZone):
        build_entry_zone(Decimal("3200"), Decimal("3200"), Direction.LONG)
