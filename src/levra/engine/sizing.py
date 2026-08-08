"""Position sizing.

    size = (capital x MAX_RISK_PCT) / |entry - stop|

MAX_RISK_PCT is imported from constants and used directly. This module exposes
no parameter, argument, or setting through which the risk fraction can be
changed — that is the point of it.
"""

from dataclasses import dataclass
from decimal import Decimal

from levra.constants import MAX_LEVERAGE, MAX_RISK_PCT
from levra.engine.rounding import quantize_money, quantize_price, quantize_size
from levra.errors import InvalidZone, StopTooTight


@dataclass(frozen=True, slots=True)
class Sizing:
    size: Decimal
    notional: Decimal
    risk_amount: Decimal
    leverage: Decimal


def size_position(capital: Decimal, entry: Decimal, stop: Decimal) -> Sizing:
    per_unit_risk = abs(entry - stop)
    if per_unit_risk == 0:
        raise InvalidZone("Entry and stop are identical — stop distance is zero.")

    risk_amount = quantize_money(capital * MAX_RISK_PCT)
    size = quantize_size(risk_amount / per_unit_risk)
    notional = quantize_money(size * entry)
    leverage = quantize_price(notional / capital)

    if leverage > MAX_LEVERAGE:
        raise StopTooTight(
            f"Stop distance of ${per_unit_risk} implies {leverage}x leverage on "
            f"${capital} capital, above the {MAX_LEVERAGE}x ceiling."
        )

    return Sizing(
        size=size, notional=notional, risk_amount=risk_amount, leverage=leverage
    )
