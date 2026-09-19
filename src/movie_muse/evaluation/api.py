"""Public surface of ``movie_muse.evaluation``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.evaluation.errors import (
    BaselineError,
    EvaluationError,
    LeverageError,
    PopulationClaimError,
)
from movie_muse.evaluation.index import INDEX_META_KEY
from movie_muse.evaluation.service import EvaluationService, assert_no_population_claim
from movie_muse.evaluation.types import (
    FORBIDDEN_POPULATION_PHRASES,
    QUALITY_BASELINE,
    SAFETY_BASELINE,
    CorrectionBurden,
    CreatorLeverage,
    EvalRun,
)

__all__ = [
    "FORBIDDEN_POPULATION_PHRASES",
    "INDEX_META_KEY",
    "QUALITY_BASELINE",
    "SAFETY_BASELINE",
    "BaselineError",
    "CorrectionBurden",
    "CreatorLeverage",
    "EvalRun",
    "EvaluationError",
    "EvaluationService",
    "LeverageError",
    "PopulationClaimError",
    "assert_no_population_claim",
]
