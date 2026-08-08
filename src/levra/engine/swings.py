"""Mechanical swing detection.

Deliberately boring: a fixed pivot rule over a fixed lookback. Nothing fitted,
nothing learned. The output must be checkable by eye against a chart.
"""

from collections.abc import Sequence

from levra.constants import PIVOT_STRENGTH, SWING_LOOKBACK_CANDLES
from levra.errors import NoValidStructuralStop
from levra.models import Candle, Direction, Swing


def _confirmed_window(candles: Sequence[Candle]) -> list[Candle]:
    confirmed = [c for c in candles if c.confirmed]
    return confirmed[-SWING_LOOKBACK_CANDLES:]


def find_pivot_lows(
    candles: Sequence[Candle], strength: int = PIVOT_STRENGTH
) -> list[Candle]:
    """Candles whose low is strictly below `strength` neighbours on both sides."""
    confirmed = [c for c in candles if c.confirmed]
    pivots: list[Candle] = []
    for i in range(strength, len(confirmed) - strength):
        window = confirmed[i - strength : i + strength + 1]
        centre = confirmed[i]
        if all(centre.low < other.low for other in window if other is not centre):
            pivots.append(centre)
    return pivots


def find_pivot_highs(
    candles: Sequence[Candle], strength: int = PIVOT_STRENGTH
) -> list[Candle]:
    """Candles whose high is strictly above `strength` neighbours on both sides."""
    confirmed = [c for c in candles if c.confirmed]
    pivots: list[Candle] = []
    for i in range(strength, len(confirmed) - strength):
        window = confirmed[i - strength : i + strength + 1]
        centre = confirmed[i]
        if all(centre.high > other.high for other in window if other is not centre):
            pivots.append(centre)
    return pivots


def find_structural_stop(candles: Sequence[Candle], direction: Direction) -> Swing:
    """Last confirmed higher-low (long) or lower-high (short) in the lookback."""
    window = _confirmed_window(candles)

    if direction is Direction.LONG:
        pivots = find_pivot_lows(window)
        if len(pivots) < 2:
            raise NoValidStructuralStop(
                "Fewer than two confirmed pivot lows in the last "
                f"{SWING_LOOKBACK_CANDLES} 4H candles — no higher-low to anchor a stop."
            )
        last, prior = pivots[-1], pivots[-2]
        if last.low <= prior.low:
            raise NoValidStructuralStop(
                "Most recent pivot low is not a higher-low — structure is not "
                "supporting a long."
            )
        return Swing(price=last.low, ts=last.ts, kind="higher_low")

    pivots = find_pivot_highs(window)
    if len(pivots) < 2:
        raise NoValidStructuralStop(
            "Fewer than two confirmed pivot highs in the last "
            f"{SWING_LOOKBACK_CANDLES} 4H candles — no lower-high to anchor a stop."
        )
    last, prior = pivots[-1], pivots[-2]
    if last.high >= prior.high:
        raise NoValidStructuralStop(
            "Most recent pivot high is not a lower-high — structure is not "
            "supporting a short."
        )
    return Swing(price=last.high, ts=last.ts, kind="lower_high")


def stop_rationale(swing: Swing) -> str:
    """Plain-English, traceable justification. Shipped on every spec."""
    label = "higher-low" if swing.kind == "higher_low" else "lower-high"
    when = swing.ts.strftime("%b %-d, %H:%M UTC")
    return (
        f"Stop placed at ${swing.price:,g} — last confirmed {label} over the past "
        f"{SWING_LOOKBACK_CANDLES} 4H candles ({when})."
    )
