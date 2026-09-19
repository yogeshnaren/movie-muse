"""Rounding, currency, and property-style money tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from movie_muse.budget.api import CurrencyError, round_money
from movie_muse.budget.engine import formula_amount


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1.225", "1.22"),
        ("1.235", "1.24"),
        ("10.5", "10.50"),
        ("0.015", "0.02"),
        ("0.025", "0.02"),
    ],
)
def test_half_even_rounding(value: str, expected: str) -> None:
    assert format(round_money(value), "f") == expected


def test_unsupported_currency_fails_closed() -> None:
    with pytest.raises(CurrencyError):
        round_money("1.00", currency="EUR")


def test_formula_rounds_once() -> None:
    amount, formula = formula_amount(
        quantity=Decimal("3"),
        rate=Decimal("1.15"),
        fringe_rate=Decimal("0.25"),
        currency="USD",
    )
    assert "half-even" in formula
    assert amount == round_money(Decimal("3") * Decimal("1.15") * Decimal("1.25"))


def test_sum_of_rounded_lines_is_stable(compiled_schedule, budget_stack) -> None:
    stored = budget_stack.budget.compile(
        compiled_schedule.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
        incentive="10.25",
    )
    left = round_money(sum((line.amount for line in stored.lines), Decimal("0")))
    right = round_money(stored.total)
    assert left == right
    for line in stored.lines:
        assert line.amount == round_money(line.amount)
        assert line.currency == "USD"
