"""Formula evaluation, reconciliation, and maturity calibration."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

from movie_muse.budget.errors import ReconciliationError, UnbackedAmountError
from movie_muse.budget.money import ZERO, parse_money, round_money
from movie_muse.budget.types import (
    Account,
    AccountClass,
    ActualEntry,
    AmountEvidence,
    BudgetClass,
    CalibrationReport,
    CalibrationSlice,
    LedgerLine,
    LineOrigin,
)
from movie_muse.schemas.api import BudgetMaturity

# Declared interval half-widths by maturity. These are bands, not accuracy claims.
DECLARED_ERROR: dict[BudgetMaturity, float] = {
    BudgetMaturity.CONCEPT_FEASIBILITY_BAND: 0.50,
    BudgetMaturity.SCRIPT_BREAKDOWN_RANGE: 0.35,
    BudgetMaturity.PRELIMINARY_PRODUCTION_ESTIMATE: 0.25,
    BudgetMaturity.DEPARTMENT_CONFIRMED_WORKING_BUDGET: 0.15,
    BudgetMaturity.BID_BACKED_ESTIMATE: 0.08,
    BudgetMaturity.PRODUCTION_FORECAST_TO_COMPLETE: 0.05,
}

DEFAULT_CHART: tuple[Account, ...] = (
    Account("1100", "Principal cast", AccountClass.ABOVE_THE_LINE, BudgetClass.LABOR, "casting"),
    Account("2100", "Shooting days", AccountClass.BELOW_THE_LINE, BudgetClass.LABOR, "ad"),
    Account("2200", "Company moves", AccountClass.BELOW_THE_LINE, BudgetClass.LOCATION, "locations"),
    Account("3100", "Contingency", AccountClass.OTHER, BudgetClass.CONTINGENCY, "producer"),
    Account("4100", "Incentive", AccountClass.OTHER, BudgetClass.INCENTIVE, "producer"),
)

ACCURACY_PHRASES = ("extremely accurate", "guaranteed accurate", "exact cost")


def formula_amount(
    *,
    quantity: Decimal,
    rate: Decimal,
    fringe_rate: Decimal,
    currency: str,
) -> tuple[Decimal, str]:
    base = parse_money(quantity) * parse_money(rate)
    fringe = base * parse_money(fringe_rate)
    amount = round_money(base + fringe, currency=currency)
    formula = (
        f"round({format(quantity, 'f')} * {format(rate, 'f')} * "
        f"(1 + {format(fringe_rate, 'f')}), half-even, {currency})"
    )
    return amount, formula


def estimate_amount(amount: Decimal, evidence: AmountEvidence, currency: str) -> Decimal:
    if not evidence.source.strip() or not evidence.as_of_date.strip():
        raise UnbackedAmountError("explicit estimates require source and as-of date")
    if evidence.currency != currency:
        raise UnbackedAmountError("estimate currency must match the ledger currency")
    return round_money(amount, currency=currency)


def reconcile(lines: Sequence[LedgerLine], total: Decimal, currency: str) -> Decimal:
    summed = round_money(sum((item.amount for item in lines), ZERO), currency=currency)
    expected = round_money(total, currency=currency)
    if summed != expected:
        raise ReconciliationError(
            f"total {format(expected, 'f')} does not equal summed lines {format(summed, 'f')}"
        )
    return summed


def require_backed(line: LedgerLine) -> None:
    if line.origin is LineOrigin.FORMULA or line.origin is LineOrigin.SCHEDULE:
        if not line.formula.strip():
            raise UnbackedAmountError(f"line {line.id} formula is empty")
        return
    if not line.evidence.source.strip() or not line.evidence.as_of_date.strip():
        raise UnbackedAmountError(f"line {line.id} estimate/override lacks evidence")


def calibrate(
    *,
    maturity: BudgetMaturity,
    lines: Sequence[LedgerLine],
    actuals: Sequence[ActualEntry],
    currency: str,
) -> CalibrationReport:
    actual_by_line = {item.line_id: item.amount for item in actuals}
    validated = bool(actuals) and maturity in {
        BudgetMaturity.BID_BACKED_ESTIMATE,
        BudgetMaturity.PRODUCTION_FORECAST_TO_COMPLETE,
    }
    declared = DECLARED_ERROR[maturity]
    buckets: dict[tuple[str, str], list[LedgerLine]] = defaultdict(list)
    for line in lines:
        buckets[("maturity", maturity.value)].append(line)
        buckets[("department", line.department)].append(line)
        buckets[("geography", line.geography)].append(line)
        buckets[("budget_class", line.budget_class.value)].append(line)
    slices: list[CalibrationSlice] = []
    for (dimension, key), members in sorted(buckets.items()):
        covered = sum(1 for item in members if item.evidence.source)
        coverage = covered / len(members) if members else 0.0
        errors: list[float] = []
        biases: list[float] = []
        for item in members:
            actual = actual_by_line.get(item.id)
            if actual is None or item.amount == ZERO:
                errors.append(declared)
                biases.append(0.0)
                continue
            forecast = float(item.amount)
            residual = float(actual - item.amount) / forecast
            errors.append(abs(residual))
            biases.append(residual)
        abs_error = sum(errors) / len(errors) if errors else declared
        bias = sum(biases) / len(biases) if biases else 0.0
        slices.append(
            CalibrationSlice(
                dimension=dimension,
                key=key,
                coverage=coverage,
                abs_error=abs_error,
                bias=bias,
                line_count=len(members),
            )
        )
    disclaimer = (
        "Measured residuals from actuals at this maturity."
        if validated
        else (
            "Declared interval only. This is not a validated accuracy claim. "
            "Do not describe the ledger as extremely accurate."
        )
    )
    return CalibrationReport(
        maturity=maturity,
        validated=validated,
        slices=tuple(slices),
        disclaimer=disclaimer,
    )


def apply_rate_delta(
    lines: Sequence[LedgerLine],
    delta: Decimal,
    currency: str,
) -> Decimal:
    total = ZERO
    factor = Decimal("1") + parse_money(delta)
    for line in lines:
        if line.budget_class is BudgetClass.INCENTIVE:
            total += line.amount
            continue
        if line.origin in {LineOrigin.FORMULA, LineOrigin.SCHEDULE}:
            amount, _formula = formula_amount(
                quantity=line.quantity,
                rate=round_money(line.rate * factor, currency=currency),
                fringe_rate=line.fringe_rate,
                currency=currency,
            )
            total += amount
        else:
            total += round_money(line.amount * factor, currency=currency)
    return round_money(total, currency=currency)
