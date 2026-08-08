"""Funding projection under a flat-rate assumption.

The current rate is held constant across the horizon. That assumption is
disclosed verbatim on every spec rather than modelled away — a simple stated
assumption is more defensible than a fragile term-structure estimate.
"""

from dataclasses import dataclass
from decimal import Decimal

from levra.engine.rounding import quantize_money
from levra.models import Direction


@dataclass(frozen=True, slots=True)
class FundingProjection:
    cost: Decimal  # signed: positive means the position pays
    intervals: int
    rate: Decimal


def project_funding(
    notional: Decimal,
    rate: Decimal,
    interval_hours: int,
    horizon_days: int,
    direction: Direction,
) -> FundingProjection:
    intervals = (horizon_days * 24) // interval_hours
    magnitude = notional * rate * Decimal(intervals)
    cost = magnitude if direction is Direction.LONG else -magnitude
    return FundingProjection(
        cost=quantize_money(cost), intervals=intervals, rate=rate
    )
