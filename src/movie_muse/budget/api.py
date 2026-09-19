"""Public surface of ``movie_muse.budget``.

Hosts and other modules must import this module, never sibling internals.
Every amount is formula-backed or an evidenced estimate. Schedule precedes budget.
"""

from __future__ import annotations

from movie_muse.budget.engine import DECLARED_ERROR, DEFAULT_CHART
from movie_muse.budget.errors import (
    AccuracyClaimError,
    BudgetError,
    BudgetNotFoundError,
    CurrencyError,
    ReconciliationError,
    ScheduleRequiredError,
    StaleBudgetError,
    UnbackedAmountError,
)
from movie_muse.budget.money import round_money
from movie_muse.budget.service import BudgetService
from movie_muse.budget.types import (
    Account,
    AccountClass,
    ActualEntry,
    AmountEvidence,
    Assumption,
    BudgetClass,
    BudgetScenario,
    CalibrationReport,
    CalibrationSlice,
    CommitmentEntry,
    LedgerLine,
    LineOrigin,
    StoredBudget,
)

__all__ = [
    "DECLARED_ERROR",
    "DEFAULT_CHART",
    "Account",
    "AccountClass",
    "AccuracyClaimError",
    "ActualEntry",
    "AmountEvidence",
    "Assumption",
    "BudgetClass",
    "BudgetError",
    "BudgetNotFoundError",
    "BudgetScenario",
    "BudgetService",
    "CalibrationReport",
    "CalibrationSlice",
    "CommitmentEntry",
    "CurrencyError",
    "LedgerLine",
    "LineOrigin",
    "ReconciliationError",
    "ScheduleRequiredError",
    "StaleBudgetError",
    "StoredBudget",
    "UnbackedAmountError",
    "round_money",
]
