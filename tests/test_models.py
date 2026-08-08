import dataclasses
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from levra.models import Candle, Conviction, Direction, Thesis


def _thesis() -> Thesis:
    return Thesis(
        asset="ETH",
        direction=Direction.LONG,
        horizon_days=30,
        conviction=Conviction.MODERATE,
        capital=Decimal("2000"),
        raw_text="ETH grinds up into September",
    )


def test_thesis_is_frozen():
    t = _thesis()
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.capital = Decimal("999999")  # type: ignore[misc]


def test_candle_is_frozen():
    c = Candle(
        ts=datetime(2026, 8, 3, 14, tzinfo=UTC),
        open=Decimal("3200"),
        high=Decimal("3250"),
        low=Decimal("3142"),
        close=Decimal("3210"),
        confirmed=True,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.low = Decimal("0")  # type: ignore[misc]
