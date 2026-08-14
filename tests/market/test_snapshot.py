"""Tests for snapshot assembly.

The behaviour worth pinning here is the deliberate asymmetry in failure
handling: a missing maintenance-margin rate degrades to the documented fallback,
while a missing price, candle set, or funding rate takes the request down.
"""

from decimal import Decimal

import httpx
import pytest
import respx

from levra.constants import DEFAULT_MAINTENANCE_MARGIN_RATE, SUPPORTED_ASSETS
from levra.errors import MarketDataError, UnsupportedAsset
from levra.market.okx import OKXClient
from levra.market.snapshot import build_snapshot, inst_id_for

OKX_BASE = "https://www.okx.com"


def _candle_rows(count: int = 30) -> list[list[str]]:
    """Newest-first rows, as OKX returns them."""
    base_ts = 1_756_656_000
    rows = []
    for i in range(count):
        ts = base_ts + (count - 1 - i) * 14_400
        low = "3190" if i == 7 else ("3150" if i == 13 else "3300")
        rows.append(
            [str(ts * 1000), "3420", "3420", low, "3310", "100", "330", "330000", "1"]
        )
    return rows


def _mock_all(rx: respx.MockRouter, *, mmr_ok: bool = True) -> respx.Route:
    """Register every upstream OKX call. Returns the candles route."""
    candles = rx.get("/api/v5/market/candles").respond(
        json={"code": "0", "data": _candle_rows()}
    )
    rx.get("/api/v5/market/ticker").respond(
        json={"code": "0", "data": [{"last": "3300"}]}
    )
    rx.get("/api/v5/public/funding-rate").respond(
        json={"code": "0", "data": [{"fundingRate": "0.0001"}]}
    )
    if mmr_ok:
        rx.get("/api/v5/public/position-tiers").respond(
            json={"code": "0", "data": [{"mmr": "0.004"}]}
        )
    else:
        rx.get("/api/v5/public/position-tiers").respond(
            json={"code": "51001", "msg": "tier lookup unavailable"}
        )
    return candles


class TestInstIdFor:
    @pytest.mark.parametrize("asset", SUPPORTED_ASSETS)
    def test_supported_assets_map_to_usdt_swaps(self, asset):
        assert inst_id_for(asset) == f"{asset}-USDT-SWAP"

    @pytest.mark.parametrize("asset", ["SOL", "DOGE", "eth", ""])
    def test_unsupported_asset_raises(self, asset):
        with pytest.raises(UnsupportedAsset):
            inst_id_for(asset)

    def test_error_names_the_supported_assets(self):
        with pytest.raises(UnsupportedAsset, match="BTC"):
            inst_id_for("SOL")


class TestBuildSnapshot:
    async def test_assembles_a_complete_snapshot(self):
        with respx.mock(base_url=OKX_BASE) as rx:
            _mock_all(rx)
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                snap = await build_snapshot(OKXClient(http), "ETH")

        assert snap.asset == "ETH"
        assert snap.mark_price == Decimal("3300")
        assert snap.funding_rate == Decimal("0.0001")
        assert snap.funding_interval_hours == 8
        assert snap.maintenance_margin_rate == Decimal("0.004")
        assert len(snap.candles) == 30
        assert snap.fetched_at.tzinfo is not None

    async def test_candles_arrive_chronological(self):
        with respx.mock(base_url=OKX_BASE) as rx:
            _mock_all(rx)
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                snap = await build_snapshot(OKXClient(http), "ETH")

        timestamps = [c.ts for c in snap.candles]
        assert timestamps == sorted(timestamps)

    async def test_unsupported_asset_rejected_before_any_request(self):
        with respx.mock(base_url=OKX_BASE, assert_all_called=False) as rx:
            route = rx.get("/api/v5/market/candles").respond(
                json={"code": "0", "data": []}
            )
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                with pytest.raises(UnsupportedAsset):
                    await build_snapshot(OKXClient(http), "SOL")

        assert not route.called

    async def test_tier_outage_degrades_to_the_fallback_rate(self):
        # The documented degradation: a tier-endpoint failure must not take the
        # endpoint down, it must fall back to the constant.
        with respx.mock(base_url=OKX_BASE) as rx:
            _mock_all(rx, mmr_ok=False)
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                snap = await build_snapshot(OKXClient(http), "ETH")

        assert snap.maintenance_margin_rate == DEFAULT_MAINTENANCE_MARGIN_RATE

    @pytest.mark.parametrize(
        "failing_path",
        [
            "/api/v5/market/candles",
            "/api/v5/market/ticker",
            "/api/v5/public/funding-rate",
        ],
    )
    async def test_essential_data_failure_propagates(self, failing_path):
        with respx.mock(base_url=OKX_BASE) as rx:
            _mock_all(rx)
            rx.get(failing_path).respond(status_code=503)
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                with pytest.raises(MarketDataError):
                    await build_snapshot(OKXClient(http), "ETH")

    async def test_requests_enough_candles_for_the_lookback(self):
        with respx.mock(base_url=OKX_BASE) as rx:
            route = _mock_all(rx)
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                await build_snapshot(OKXClient(http), "ETH")

        limit = int(route.calls[0].request.url.params["limit"])
        # 20-candle lookback plus pivot strength on both sides, plus headroom.
        assert limit >= 24
