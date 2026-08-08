import dataclasses
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from levra.engine.swings import find_pivot_lows, find_structural_stop, stop_rationale
from levra.errors import NoValidStructuralStop
from levra.models import Candle, Direction, Swing

START = datetime(2026, 8, 1, tzinfo=UTC)


def candles_from_lows(lows: list[str]) -> tuple[Candle, ...]:
    """Build confirmed 4H candles with the given lows; highs sit 100 above."""
    return tuple(
        Candle(
            ts=START + timedelta(hours=4 * i),
            open=Decimal(low) + Decimal("50"),
            high=Decimal(low) + Decimal("100"),
            low=Decimal(low),
            close=Decimal(low) + Decimal("60"),
            confirmed=True,
        )
        for i, low in enumerate(lows)
    )


def test_finds_a_single_pivot_low():
    c = candles_from_lows(["110", "108", "100", "108", "112"])
    pivots = find_pivot_lows(c)
    assert [p.low for p in pivots] == [Decimal("100")]


def test_ignores_pivot_without_enough_candles_to_its_right():
    c = candles_from_lows(["110", "108", "106", "104", "100"])
    assert find_pivot_lows(c) == []


def test_ignores_unconfirmed_candles():
    c = list(candles_from_lows(["110", "108", "100", "108", "112"]))
    c[2] = dataclasses.replace(c[2], confirmed=False)
    assert find_pivot_lows(tuple(c)) == []


def test_structural_stop_is_the_most_recent_higher_low():
    c = candles_from_lows(["110", "108", "100", "108", "112", "109", "105", "111", "115"])
    swing = find_structural_stop(c, Direction.LONG)
    assert swing.price == Decimal("105")
    assert swing.kind == "higher_low"
    assert swing.ts == START + timedelta(hours=4 * 6)


def test_rejects_when_latest_pivot_is_a_lower_low():
    c = candles_from_lows(["115", "111", "105", "111", "112", "108", "100", "108", "110"])
    with pytest.raises(NoValidStructuralStop):
        find_structural_stop(c, Direction.LONG)


def test_rejects_when_only_one_pivot_exists():
    c = candles_from_lows(["110", "108", "100", "108", "112"])
    with pytest.raises(NoValidStructuralStop):
        find_structural_stop(c, Direction.LONG)


def test_short_uses_lower_highs():
    c = candles_from_lows(["100", "102", "110", "102", "98", "101", "105", "99", "95"])
    swing = find_structural_stop(c, Direction.SHORT)
    assert swing.price == Decimal("205")
    assert swing.kind == "lower_high"


def test_only_the_last_20_candles_are_considered():
    old = ["110", "108", "100", "108", "112", "109", "105", "111", "115", "116"]
    filler = ["120"] * 20
    with pytest.raises(NoValidStructuralStop):
        find_structural_stop(candles_from_lows(old + filler), Direction.LONG)


def test_stop_rationale_names_price_rule_and_timestamp():
    swing = Swing(
        price=Decimal("3142"),
        ts=datetime(2026, 8, 3, 14, tzinfo=UTC),
        kind="higher_low",
    )
    text = stop_rationale(swing)
    assert ",142" in text
    assert "higher-low" in text
    assert "20 4H candles" in text
