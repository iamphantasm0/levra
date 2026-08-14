"""Tests for deterministic spec hashing and chain logging."""

from decimal import Decimal

import pytest

from levra.chain import hash_spec, hash_spec_hex, log_to_chain
from levra.engine.build import build_spec
from levra.models import (
    Candle,
    Conviction,
    Direction,
    MarketSnapshot,
    Thesis,
)


@pytest.fixture
def spec():
    from datetime import UTC, datetime

    start = datetime(2026, 8, 1, tzinfo=UTC)
    lows = ["3200", "3180", "3150", "3180", "3205", "3210", "3190", "3205", "3215"]
    candles = tuple(
        Candle(
            ts=start.replace(hour=(i * 4) % 24, day=1 + (i * 4) // 24),
            open=Decimal(low),
            high=Decimal(low) + Decimal("120"),
            low=Decimal(low),
            close=Decimal(low) + Decimal("60"),
            confirmed=True,
        )
        for i, low in enumerate(lows)
    )
    snapshot = MarketSnapshot(
        asset="ETH",
        mark_price=Decimal("3300"),
        candles=candles,
        funding_rate=Decimal("0.0001"),
        funding_interval_hours=8,
        maintenance_margin_rate=Decimal("0.005"),
        fetched_at=start,
    )
    thesis = Thesis(
        asset="ETH",
        direction=Direction.LONG,
        horizon_days=30,
        conviction=Conviction.MODERATE,
        capital=Decimal("2000"),
        raw_text="Long ETH 30d",
    )
    return build_spec(thesis, snapshot)


class TestHashSpec:
    def test_hash_is_32_bytes(self, spec):
        h = hash_spec(spec)
        assert len(h) == 32

    def test_hash_is_deterministic(self, spec):
        h1 = hash_spec(spec)
        h2 = hash_spec(spec)
        assert h1 == h2

    def test_hash_hex_produces_0x_prefixed_string(self, spec):
        h = hash_spec_hex(spec)
        assert h.startswith("0x")
        assert len(h) == 66

    def test_different_specs_produce_different_hashes(self, spec):
        from datetime import UTC, datetime

        from levra.engine.build import build_spec
        from levra.models import (
            Candle,
            Conviction,
            Direction,
            MarketSnapshot,
            Thesis,
        )

        start = datetime(2026, 8, 1, tzinfo=UTC)
        highs = ["52000"] * 30
        highs[12] = "52200"
        highs[18] = "52100"
        lows = ["50000"] * 30
        candles = tuple(
            Candle(
                ts=start.replace(hour=(i * 4) % 24, day=1 + (i * 4) // 24),
                open=Decimal(lows[i]),
                high=Decimal(highs[i]),
                low=Decimal(lows[i]),
                close=Decimal(lows[i]) + Decimal("250"),
                confirmed=True,
            )
            for i in range(len(lows))
        )
        snapshot2 = MarketSnapshot(
            asset="BTC",
            mark_price=Decimal("51000"),
            candles=candles,
            funding_rate=Decimal("0.00015"),
            funding_interval_hours=8,
            maintenance_margin_rate=Decimal("0.005"),
            fetched_at=start,
        )
        thesis2 = Thesis(
            asset="BTC",
            direction=Direction.SHORT,
            horizon_days=14,
            conviction=Conviction.HIGH,
            capital=Decimal("5000"),
            raw_text="Short BTC 14d",
        )
        spec2 = build_spec(thesis2, snapshot2)
        assert hash_spec(spec) != hash_spec(spec2)


class TestLogToChain:
    async def test_log_to_chain_is_non_fatal(self, spec):
        await log_to_chain(spec)

    async def test_log_to_chain_with_none_url_does_not_crash(self, spec):
        await log_to_chain(spec, rpc_url=None)