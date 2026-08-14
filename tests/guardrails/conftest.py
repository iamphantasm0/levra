from datetime import UTC, datetime
from decimal import Decimal

import pytest

from levra.engine.build import build_spec
from levra.models import Candle, Conviction, Direction, MarketSnapshot, Thesis

EXPECTED_STOP = Decimal("3190")

_LOWS = ["3200", "3180", "3150", "3180", "3205", "3210", "3190", "3205", "3215"]


@pytest.fixture
def snapshot() -> MarketSnapshot:
    start = datetime(2026, 8, 1, tzinfo=UTC)
    candles = tuple(
        Candle(
            ts=start.replace(hour=(i * 4) % 24, day=1 + (i * 4) // 24),
            open=Decimal(low),
            high=Decimal(low) + Decimal("120"),
            low=Decimal(low),
            close=Decimal(low) + Decimal("60"),
            confirmed=True,
        )
        for i, low in enumerate(_LOWS)
    )
    return MarketSnapshot(
        asset="ETH",
        mark_price=Decimal("3300"),
        candles=candles,
        funding_rate=Decimal("0.0001"),
        funding_interval_hours=8,
        maintenance_margin_rate=Decimal("0.005"),
        fetched_at=start,
    )


@pytest.fixture
def thesis() -> Thesis:
    return Thesis(
        asset="ETH",
        direction=Direction.LONG,
        horizon_days=30,
        conviction=Conviction.MODERATE,
        capital=Decimal("2000"),
        raw_text="Long ETH 30d moderate $2000",
    )


@pytest.fixture
def spec(thesis, snapshot):
    return build_spec(thesis, snapshot)
