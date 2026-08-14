from datetime import UTC, datetime
from decimal import Decimal

import httpx

from levra.constants import SWING_TIMEFRAME
from levra.errors import MarketDataError
from levra.models import Candle


class OKXClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def fetch_candles(
        self,
        inst_id: str,
        bar: str = SWING_TIMEFRAME,
        limit: int = 100,
    ) -> tuple[Candle, ...]:
        resp = await self._http.get(
            "/api/v5/market/candles",
            params={"instId": inst_id, "bar": bar, "limit": str(limit)},
        )
        if resp.status_code >= 500:
            raise MarketDataError(f"OKX 5xx: {resp.status_code}")
        body = resp.json()
        if body.get("code") != "0":
            raise MarketDataError(f"OKX error: {body.get('msg', 'unknown')}")
        raw = body["data"]
        candles: list[Candle] = []
        for entry in reversed(raw):
            if entry[8] != "1":
                continue
            candles.append(
                Candle(
                    ts=datetime.fromtimestamp(int(entry[0]) / 1000, tz=UTC),
                    open=Decimal(entry[1]),
                    high=Decimal(entry[2]),
                    low=Decimal(entry[3]),
                    close=Decimal(entry[4]),
                    confirmed=True,
                )
            )
        return tuple(candles)

    async def fetch_funding(self, inst_id: str) -> tuple[Decimal, int]:
        resp = await self._http.get(
            "/api/v5/public/funding-rate",
            params={"instId": inst_id},
        )
        if resp.status_code >= 500:
            raise MarketDataError(f"OKX 5xx: {resp.status_code}")
        body = resp.json()
        if body.get("code") != "0":
            raise MarketDataError(f"OKX error: {body.get('msg', 'unknown')}")
        rate = Decimal(body["data"][0]["fundingRate"])
        return (rate, 8)

    async def fetch_mark_price(self, inst_id: str) -> Decimal:
        resp = await self._http.get(
            "/api/v5/market/ticker",
            params={"instId": inst_id},
        )
        if resp.status_code >= 500:
            raise MarketDataError(f"OKX 5xx: {resp.status_code}")
        body = resp.json()
        if body.get("code") != "0":
            raise MarketDataError(f"OKX error: {body.get('msg', 'unknown')}")
        return Decimal(body["data"][0]["last"])

    async def fetch_maintenance_margin_rate(self, inst_family: str) -> Decimal:
        resp = await self._http.get(
            "/api/v5/public/position-tiers",
            params={
                "instType": "SWAP",
                "tdMode": "isolated",
                "instFamily": inst_family,
            },
        )
        if resp.status_code >= 500:
            raise MarketDataError(f"OKX 5xx: {resp.status_code}")
        body = resp.json()
        if body.get("code") != "0":
            raise MarketDataError(f"OKX error: {body.get('msg', 'unknown')}")
        return Decimal(body["data"][0]["mmr"])
