from datetime import UTC, datetime
from decimal import Decimal

import pytest

from levra.constants import FUNDING_ASSUMPTION_DISCLOSURE, RISK_RULE_DISCLOSURE
from levra.engine.build import build_spec
from levra.errors import UnsupportedAsset
from levra.models import Candle, Conviction, Direction, MarketSnapshot, Thesis

START = datetime(2026, 8, 1, tzinfo=UTC)


def _snapshot(asset: str = "ETH") -> MarketSnapshot:
    lows = ["3200", "3180", "3150", "3180", "3205", "3210", "3190", "3205", "3215"]
    candles = tuple(
        Candle(
            ts=START.replace(hour=(i * 4) % 24, day=1 + (i * 4) // 24),
            open=Decimal(low),
            high=Decimal(low) + Decimal("120"),
            low=Decimal(low),
            close=Decimal(low) + Decimal("60"),
            confirmed=True,
        )
        for i, low in enumerate(lows)
    )
    return MarketSnapshot(
        asset=asset,
        mark_price=Decimal("3300"),
        candles=candles,
        funding_rate=Decimal("0.0001"),
        funding_interval_hours=8,
        maintenance_margin_rate=Decimal("0.005"),
        fetched_at=START,
    )


def _thesis(asset: str = "ETH") -> Thesis:
    return Thesis(
        asset=asset,
        direction=Direction.LONG,
        horizon_days=30,
        conviction=Conviction.MODERATE,
        capital=Decimal("2000"),
        raw_text="I think ETH grinds up into September",
    )


def test_rejects_an_unsupported_asset_before_touching_the_engine():
    with pytest.raises(UnsupportedAsset):
        build_spec(_thesis("SOL"), _snapshot("SOL"))


def test_stop_comes_from_the_swing_engine():
    spec = build_spec(_thesis(), _snapshot())
    assert spec.stop == Decimal("3190")


def test_entry_zone_high_is_the_mark_price_for_a_long():
    spec = build_spec(_thesis(), _snapshot())
    assert spec.entry_zone.high == Decimal("3300.00")


def test_size_is_derived_from_the_sizing_edge_not_the_zone_low():
    spec = build_spec(_thesis(), _snapshot())
    assert spec.position_size == Decimal("0.363636")


def test_risk_amount_is_two_percent():
    spec = build_spec(_thesis(), _snapshot())
    assert spec.risk_amount == Decimal("40.00")


def test_disclosures_are_the_verbatim_constants():
    spec = build_spec(_thesis(), _snapshot())
    assert spec.risk_rule == RISK_RULE_DISCLOSURE
    assert spec.funding_assumption == FUNDING_ASSUMPTION_DISCLOSURE


def test_stop_rationale_is_populated_and_names_the_lookback():
    spec = build_spec(_thesis(), _snapshot())
    assert "20 4H candles" in spec.stop_rationale
    assert "higher-low" in spec.stop_rationale


def test_liquidation_is_further_away_than_the_stop():
    spec = build_spec(_thesis(), _snapshot())
    assert spec.liquidation_buffer_ratio > Decimal("1")


def test_conviction_is_carried_through_without_affecting_size():
    low = build_spec(
        Thesis(
            asset="ETH",
            direction=Direction.LONG,
            horizon_days=30,
            conviction=Conviction.LOW,
            capital=Decimal("2000"),
            raw_text="x",
        ),
        _snapshot(),
    )
    high = build_spec(
        Thesis(
            asset="ETH",
            direction=Direction.LONG,
            horizon_days=30,
            conviction=Conviction.HIGH,
            capital=Decimal("2000"),
            raw_text="x",
        ),
        _snapshot(),
    )
    assert low.conviction is Conviction.LOW
    assert high.conviction is Conviction.HIGH
    assert low.position_size == high.position_size
