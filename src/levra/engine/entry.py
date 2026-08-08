"""Entry zone construction.

The zone runs from the mark price toward the stop by a fixed fraction of the
mark-to-stop distance. `sizing_edge` is the edge furthest from the stop, so
sizing from it guarantees any fill inside the zone risks at most the budget.
"""

from decimal import Decimal

from levra.constants import ENTRY_ZONE_STOP_DISTANCE_FRACTION
from levra.engine.rounding import quantize_price
from levra.errors import InvalidZone
from levra.models import Direction, EntryZone


def build_entry_zone(mark: Decimal, stop: Decimal, direction: Direction) -> EntryZone:
    if direction is Direction.LONG and stop >= mark:
        raise InvalidZone(
            f"Long stop ${stop} is not below the mark price ${mark}."
        )
    if direction is Direction.SHORT and stop <= mark:
        raise InvalidZone(
            f"Short stop ${stop} is not above the mark price ${mark}."
        )

    distance = abs(mark - stop)
    offset = distance * ENTRY_ZONE_STOP_DISTANCE_FRACTION

    if direction is Direction.LONG:
        low = quantize_price(mark - offset)
        high = quantize_price(mark)
        return EntryZone(low=low, high=high, sizing_edge=high)

    low = quantize_price(mark)
    high = quantize_price(mark + offset)
    return EntryZone(low=low, high=high, sizing_edge=low)
