"""Public surface of ``movie_muse.commercial_forecast``.

Hosts and other modules must import this module, never sibling internals.
Commercial scenarios are P10/P50/P90 ranges, never a guaranteed number.
"""

from __future__ import annotations

from movie_muse.commercial_forecast.errors import (
    AssumptionError,
    ForecastError,
    ForecastNotFoundError,
    GuaranteeClaimError,
    InsufficientEvidenceError,
    LeakageError,
    UntracedNumberError,
)
from movie_muse.commercial_forecast.service import CommercialForecastService, assert_no_guarantee
from movie_muse.commercial_forecast.types import (
    DISCLAIMER,
    FORBIDDEN_GUARANTEE_PHRASES,
    INSUFFICIENT_EVIDENCE,
    MIN_IN_DISTRIBUTION,
    MODEL_VERSION,
    REQUIRED_ASSUMPTIONS,
    AssumptionKey,
    BacktestReport,
    CommercialForecast,
    ComparableTitle,
    ForecastAssumption,
    NumberTrace,
    SensitivityReport,
)

__all__ = [
    "DISCLAIMER",
    "FORBIDDEN_GUARANTEE_PHRASES",
    "INSUFFICIENT_EVIDENCE",
    "MIN_IN_DISTRIBUTION",
    "MODEL_VERSION",
    "REQUIRED_ASSUMPTIONS",
    "AssumptionError",
    "AssumptionKey",
    "BacktestReport",
    "CommercialForecast",
    "CommercialForecastService",
    "ComparableTitle",
    "ForecastAssumption",
    "ForecastError",
    "ForecastNotFoundError",
    "GuaranteeClaimError",
    "InsufficientEvidenceError",
    "LeakageError",
    "NumberTrace",
    "SensitivityReport",
    "UntracedNumberError",
    "assert_no_guarantee",
]
