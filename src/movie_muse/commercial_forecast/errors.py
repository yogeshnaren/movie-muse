"""Typed failures for commercial scenario forecasting."""

from __future__ import annotations


class ForecastError(RuntimeError):
    """Base class for commercial forecast failures."""


class ForecastNotFoundError(ForecastError):
    """The named scenario is not in the index."""


class InsufficientEvidenceError(ForecastError):
    """Poor coverage or out-of-distribution inputs cannot emit a scenario."""


class LeakageError(ForecastError):
    """Backtests and forecasts must not use data dated after the as-of cutoff."""


class UntracedNumberError(ForecastError):
    """Every scenario number must cite data, method, and assumptions."""


class GuaranteeClaimError(ForecastError):
    """Commercial scenarios are ranges, not a single guaranteed number."""


class AssumptionError(ForecastError):
    """Required distribution/marketing/release/territory/talent/platform assumptions."""
