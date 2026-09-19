"""Typed failures for the budget evidence ledger."""

from __future__ import annotations


class BudgetError(RuntimeError):
    """Base class for budget failures."""


class BudgetNotFoundError(BudgetError):
    """The named budget is not in the index."""


class StaleBudgetError(BudgetError):
    """A stale or schedule-stale budget cannot be treated as current."""


class UnbackedAmountError(BudgetError):
    """Every amount must be formula-backed or an explicit estimate with evidence."""


class ReconciliationError(BudgetError):
    """Reported totals do not equal the sum of rounded line amounts."""


class CurrencyError(BudgetError):
    """Mixed currencies or invalid rounding."""


class AccuracyClaimError(BudgetError):
    """An accuracy claim is not supported by maturity and calibration."""


class ScheduleRequiredError(BudgetError):
    """A current schedule must precede the budget evidence ledger."""
