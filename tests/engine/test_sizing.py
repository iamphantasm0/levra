import inspect
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from levra.constants import MAX_RISK_PCT
from levra.engine.sizing import size_position
from levra.errors import StopTooTight


def test_risk_amount_is_two_percent_of_capital():
    s = size_position(Decimal("2000"), Decimal("3200"), Decimal("3100"))
    assert s.risk_amount == Decimal("40.00")


def test_size_is_risk_divided_by_stop_distance():
    s = size_position(Decimal("2000"), Decimal("3200"), Decimal("3100"))
    assert s.size == Decimal("0.400000")


def test_notional_is_size_times_entry():
    s = size_position(Decimal("2000"), Decimal("3200"), Decimal("3100"))
    assert s.notional == Decimal("1280.00")


def test_leverage_is_notional_over_capital():
    s = size_position(Decimal("2000"), Decimal("3200"), Decimal("3100"))
    assert s.leverage == Decimal("0.64")


def test_works_for_shorts_where_stop_is_above_entry():
    s = size_position(Decimal("2000"), Decimal("3200"), Decimal("3300"))
    assert s.size == Decimal("0.400000")


def test_rejects_a_stop_so_tight_it_implies_excess_leverage():
    with pytest.raises(StopTooTight):
        size_position(Decimal("2000"), Decimal("3200"), Decimal("3199"))


def test_signature_exposes_no_risk_parameter():
    params = set(inspect.signature(size_position).parameters)
    assert params == {"capital", "entry", "stop"}


@settings(max_examples=200)
@given(
    capital=st.decimals(min_value=100, max_value=1_000_000, places=2),
    entry=st.decimals(min_value=1000, max_value=200_000, places=2),
    gap_pct=st.decimals(min_value="0.02", max_value="0.5", places=4),
)
def test_realised_risk_never_exceeds_two_percent(capital, entry, gap_pct):
    stop = (entry * (1 - gap_pct)).quantize(Decimal("0.01"))
    try:
        s = size_position(capital, entry, stop)
    except StopTooTight:
        return
    realised = s.size * abs(entry - stop)
    assert realised <= capital * MAX_RISK_PCT
