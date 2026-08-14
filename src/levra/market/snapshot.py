import asyncio
from datetime import UTC, datetime

from levra.constants import (
    DEFAULT_MAINTENANCE_MARGIN_RATE,
    PIVOT_STRENGTH,
    SUPPORTED_ASSETS,
    SWING_LOOKBACK_CANDLES,
    SWING_TIMEFRAME,
)
from levra.errors import MarketDataError, UnsupportedAsset
from levra.market.okx import OKXClient
from levra.models import MarketSnapshot

ASSET_INST_ID: dict[str, str] = {a: f"{a}-USDT-SWAP" for a in SUPPORTED_ASSETS}
ASSET_INST_FAMILY: dict[str, str] = {a: f"{a}-USDT" for a in SUPPORTED_ASSETS}

_CANDLE_LIMIT = SWING_LOOKBACK_CANDLES + PIVOT_STRENGTH + 5


def inst_id_for(asset: str) -> str:
    try:
        return ASSET_INST_ID[asset]
    except KeyError:
        raise UnsupportedAsset(
            f"{asset} is not supported. Supported: {', '.join(SUPPORTED_ASSETS)}"
        ) from None


async def build_snapshot(client: OKXClient, asset: str) -> MarketSnapshot:
    inst_id = inst_id_for(asset)
    inst_family = ASSET_INST_FAMILY[asset]

    tasks = [
        client.fetch_candles(inst_id, bar=SWING_TIMEFRAME, limit=_CANDLE_LIMIT),
        client.fetch_funding(inst_id),
        client.fetch_mark_price(inst_id),
        client.fetch_maintenance_margin_rate(inst_family),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    candles, funding, mark_price, mmr = results

    if isinstance(candles, BaseException):
        raise candles
    if isinstance(funding, BaseException):
        raise funding
    if isinstance(mark_price, BaseException):
        raise mark_price

    funding_rate, funding_interval = funding  # type: ignore[unused-ignore, has-type, misc]

    if isinstance(mmr, BaseException):
        if isinstance(mmr, MarketDataError):
            maintenance_margin_rate = DEFAULT_MAINTENANCE_MARGIN_RATE
        else:
            raise mmr
    else:
        maintenance_margin_rate = mmr  # type: ignore[unused-ignore, assignment]

    return MarketSnapshot(
        asset=asset,
        mark_price=mark_price,  # type: ignore[unused-ignore, arg-type]
        candles=candles,  # type: ignore[unused-ignore, arg-type]
        funding_rate=funding_rate,  # type: ignore[has-type]
        funding_interval_hours=funding_interval,  # type: ignore[has-type]
        maintenance_margin_rate=maintenance_margin_rate,
        fetched_at=datetime.now(tz=UTC),
    )
