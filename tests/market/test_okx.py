"""Tests for the OKX public market client.

This layer is the source of every number that reaches a spec, so the cases that
matter are the parsing contracts: candle ordering, the confirm flag, and Decimal
discipline at the boundary where OKX hands us strings.
"""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
import respx

from levra.errors import MarketDataError
from levra.market.okx import OKXClient

OKX_BASE = "https://www.okx.com"


def _candle(ts_ms: int, low: str, confirm: str = "1") -> list[str]:
    """One OKX candle row: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]."""
    return [str(ts_ms), "3400", "3450", low, "3420", "100", "330", "330000", confirm]


async def _client(rx: respx.MockRouter) -> OKXClient:  # noqa: ARG001
    return OKXClient(httpx.AsyncClient(base_url=OKX_BASE))


class TestFetchCandles:
    async def test_reverses_okx_ordering_into_chronological(self):
        # OKX returns newest-first; the client must hand back oldest-first.
        newest, middle, oldest = 1_756_684_800_000, 1_756_670_400_000, 1_756_656_000_000
        data = [
            _candle(newest, "3300"),
            _candle(middle, "3200"),
            _candle(oldest, "3100"),
        ]
        with respx.mock(base_url=OKX_BASE) as rx:
            rx.get("/api/v5/market/candles").respond(json={"code": "0", "data": data})
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                candles = await OKXClient(http).fetch_candles("ETH-USDT-SWAP")

        assert [c.low for c in candles] == [
            Decimal("3100"),
            Decimal("3200"),
            Decimal("3300"),
        ]
        assert candles[0].ts < candles[-1].ts

    async def test_skips_unconfirmed_candles(self):
        data = [
            _candle(1_756_684_800_000, "3300", confirm="0"),
            _candle(1_756_670_400_000, "3200", confirm="1"),
        ]
        with respx.mock(base_url=OKX_BASE) as rx:
            rx.get("/api/v5/market/candles").respond(json={"code": "0", "data": data})
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                candles = await OKXClient(http).fetch_candles("ETH-USDT-SWAP")

        assert len(candles) == 1
        assert candles[0].low == Decimal("3200")
        assert all(c.confirmed for c in candles)

    async def test_prices_are_decimal_not_float(self):
        # 3182.15 is not representable exactly as a float; going through float
        # would change the value. This is the boundary the project cares about.
        data = [_candle(1_756_684_800_000, "3182.15")]
        with respx.mock(base_url=OKX_BASE) as rx:
            rx.get("/api/v5/market/candles").respond(json={"code": "0", "data": data})
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                candles = await OKXClient(http).fetch_candles("ETH-USDT-SWAP")

        low = candles[0].low
        assert isinstance(low, Decimal)
        assert low == Decimal("3182.15")
        assert str(low) == "3182.15"

    async def test_timestamp_is_utc_from_milliseconds(self):
        ts_ms = 1_756_684_800_000
        data = [_candle(ts_ms, "3300")]
        with respx.mock(base_url=OKX_BASE) as rx:
            rx.get("/api/v5/market/candles").respond(json={"code": "0", "data": data})
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                candles = await OKXClient(http).fetch_candles("ETH-USDT-SWAP")

        assert candles[0].ts == datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        assert candles[0].ts.tzinfo == UTC

    async def test_sends_expected_query_params(self):
        with respx.mock(base_url=OKX_BASE) as rx:
            route = rx.get("/api/v5/market/candles").respond(
                json={"code": "0", "data": []}
            )
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                await OKXClient(http).fetch_candles("BTC-USDT-SWAP", bar="4H", limit=27)

        request = route.calls[0].request
        assert request.url.params["instId"] == "BTC-USDT-SWAP"
        assert request.url.params["bar"] == "4H"
        assert request.url.params["limit"] == "27"

    async def test_empty_data_returns_empty_tuple(self):
        with respx.mock(base_url=OKX_BASE) as rx:
            rx.get("/api/v5/market/candles").respond(json={"code": "0", "data": []})
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                candles = await OKXClient(http).fetch_candles("ETH-USDT-SWAP")

        assert candles == ()


class TestErrorEnvelopes:
    @pytest.mark.parametrize(
        ("path", "method", "args"),
        [
            ("/api/v5/market/candles", "fetch_candles", ("ETH-USDT-SWAP",)),
            ("/api/v5/public/funding-rate", "fetch_funding", ("ETH-USDT-SWAP",)),
            ("/api/v5/market/ticker", "fetch_mark_price", ("ETH-USDT-SWAP",)),
            (
                "/api/v5/public/position-tiers",
                "fetch_maintenance_margin_rate",
                ("ETH-USDT",),
            ),
        ],
    )
    async def test_non_zero_code_raises_market_data_error(self, path, method, args):
        with respx.mock(base_url=OKX_BASE) as rx:
            rx.get(path).respond(json={"code": "51001", "msg": "Instrument ID error"})
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                client = OKXClient(http)
                with pytest.raises(MarketDataError, match="Instrument ID error"):
                    await getattr(client, method)(*args)

    @pytest.mark.parametrize(
        ("path", "method", "args"),
        [
            ("/api/v5/market/candles", "fetch_candles", ("ETH-USDT-SWAP",)),
            ("/api/v5/public/funding-rate", "fetch_funding", ("ETH-USDT-SWAP",)),
            ("/api/v5/market/ticker", "fetch_mark_price", ("ETH-USDT-SWAP",)),
            (
                "/api/v5/public/position-tiers",
                "fetch_maintenance_margin_rate",
                ("ETH-USDT",),
            ),
        ],
    )
    async def test_5xx_raises_market_data_error(self, path, method, args):
        with respx.mock(base_url=OKX_BASE) as rx:
            rx.get(path).respond(status_code=503)
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                client = OKXClient(http)
                with pytest.raises(MarketDataError, match="5xx"):
                    await getattr(client, method)(*args)


class TestFetchFunding:
    async def test_returns_decimal_rate_and_eight_hour_interval(self):
        with respx.mock(base_url=OKX_BASE) as rx:
            rx.get("/api/v5/public/funding-rate").respond(
                json={"code": "0", "data": [{"fundingRate": "0.00012345"}]}
            )
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                rate, interval = await OKXClient(http).fetch_funding("ETH-USDT-SWAP")

        assert isinstance(rate, Decimal)
        assert rate == Decimal("0.00012345")
        assert interval == 8

    async def test_negative_funding_rate_is_preserved(self):
        with respx.mock(base_url=OKX_BASE) as rx:
            rx.get("/api/v5/public/funding-rate").respond(
                json={"code": "0", "data": [{"fundingRate": "-0.00008"}]}
            )
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                rate, _ = await OKXClient(http).fetch_funding("ETH-USDT-SWAP")

        assert rate == Decimal("-0.00008")


class TestFetchMarkPrice:
    async def test_returns_last_as_decimal(self):
        with respx.mock(base_url=OKX_BASE) as rx:
            rx.get("/api/v5/market/ticker").respond(
                json={"code": "0", "data": [{"last": "3301.45"}]}
            )
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                price = await OKXClient(http).fetch_mark_price("ETH-USDT-SWAP")

        assert isinstance(price, Decimal)
        assert price == Decimal("3301.45")


class TestFetchMaintenanceMarginRate:
    async def test_returns_mmr_as_decimal(self):
        with respx.mock(base_url=OKX_BASE) as rx:
            rx.get("/api/v5/public/position-tiers").respond(
                json={"code": "0", "data": [{"mmr": "0.005"}]}
            )
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                mmr = await OKXClient(http).fetch_maintenance_margin_rate("ETH-USDT")

        assert isinstance(mmr, Decimal)
        assert mmr == Decimal("0.005")

    async def test_sends_isolated_swap_params(self):
        with respx.mock(base_url=OKX_BASE) as rx:
            route = rx.get("/api/v5/public/position-tiers").respond(
                json={"code": "0", "data": [{"mmr": "0.005"}]}
            )
            async with httpx.AsyncClient(base_url=OKX_BASE) as http:
                await OKXClient(http).fetch_maintenance_margin_rate("BTC-USDT")

        params = route.calls[0].request.url.params
        assert params["instType"] == "SWAP"
        assert params["tdMode"] == "isolated"
        assert params["instFamily"] == "BTC-USDT"
