"""Liquidation estimate from isolated-margin arithmetic.

No liquidation-cluster data. This is the deterministic price at which the
position's own margin is exhausted, plus how far that is relative to the stop.
"""

from dataclasses import dataclass
from decimal import Decimal

from levra.engine.rounding import quantize_price
from levra.models import Direction


@dataclass(frozen=True, slots=True)
class Liquidation:
    price: Decimal
    buffer_ratio: Decimal  # |liq - entry| / |entry - stop|


def project_liquidation(
    entry: Decimal,
    stop: Decimal,
    leverage: Decimal,
    maintenance_margin_rate: Decimal,
    direction: Direction,
) -> Liquidation:
    inverse_leverage = Decimal(1) / leverage

    if direction is Direction.LONG:
        raw = entry * (Decimal(1) - inverse_leverage + maintenance_margin_rate)
    else:
        raw = entry * (Decimal(1) + inverse_leverage - maintenance_margin_rate)

    price = quantize_price(raw)
    stop_distance = abs(entry - stop)
    buffer_ratio = quantize_price(abs(price - entry) / stop_distance)
    return Liquidation(price=price, buffer_ratio=buffer_ratio)
