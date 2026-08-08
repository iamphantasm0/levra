from decimal import Decimal

from levra.engine.rounding import quantize_money, quantize_price, quantize_size


def test_price_rounds_to_two_places():
    assert quantize_price(Decimal("3142.005")) == Decimal("3142.01")


def test_size_always_rounds_down():
    # Rounding size up would push realised risk above the 2% budget.
    assert quantize_size(Decimal("0.6896999999")) == Decimal("0.689699")


def test_money_rounds_to_cents():
    assert quantize_money(Decimal("40.006")) == Decimal("40.00")
