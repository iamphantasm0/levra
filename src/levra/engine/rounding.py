"""Quantisation. Size rounds down so realised risk can only ever undershoot."""

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Final

_PRICE_QUANTUM: Final[Decimal] = Decimal("0.01")
_SIZE_QUANTUM: Final[Decimal] = Decimal("0.000001")
_MONEY_QUANTUM: Final[Decimal] = Decimal("0.01")


def quantize_price(value: Decimal) -> Decimal:
    return value.quantize(_PRICE_QUANTUM, rounding=ROUND_HALF_UP)


def quantize_size(value: Decimal) -> Decimal:
    return value.quantize(_SIZE_QUANTUM, rounding=ROUND_DOWN)


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANTUM, rounding=ROUND_DOWN)
