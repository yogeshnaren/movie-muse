"""Decimal money helpers. Amounts round once, half-even, to currency minor units."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from movie_muse.budget.errors import CurrencyError

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")


def parse_money(value: Decimal | int | str) -> Decimal:
    if isinstance(value, Decimal):
        parsed = value
    else:
        parsed = Decimal(str(value))
    if not parsed.is_finite():
        raise CurrencyError("amount is not a finite decimal")
    return parsed


def round_money(value: Decimal | int | str, *, currency: str = "USD") -> Decimal:
    if currency != "USD":
        raise CurrencyError(f"unsupported currency {currency}")
    return parse_money(value).quantize(CENTS, rounding=ROUND_HALF_EVEN)


def money_str(value: Decimal) -> str:
    return format(round_money(value), "f")
