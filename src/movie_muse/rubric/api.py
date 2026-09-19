"""Public surface of ``movie_muse.rubric``.

Hosts and other modules must import this module, never sibling internals.
Rubric analysis is advisory and never a FilmIR or CreativeIntentIR write.
"""

from __future__ import annotations

from movie_muse.rubric.errors import (
    AdvisoryLabelError,
    AnalysisNotFoundError,
    CalibrationError,
    EvidenceLinkError,
    OverrideDeniedError,
    RatingNotFoundError,
    RubricError,
    RubricNotFoundError,
    UnexplainedScoreError,
)
from movie_muse.rubric.service import RubricService
from movie_muse.rubric.types import (
    DISCLAIMER,
    REQUIRED_CRITERIA,
    CalibrationReport,
    CounterEvidence,
    CreatorOverride,
    CriterionKind,
    CriterionSpec,
    DisagreementReport,
    RaterKind,
    Rating,
    RubricAnalysis,
    RubricDefinition,
    ScoreTrace,
    default_criteria,
)

__all__ = [
    "DISCLAIMER",
    "REQUIRED_CRITERIA",
    "AdvisoryLabelError",
    "AnalysisNotFoundError",
    "CalibrationError",
    "CalibrationReport",
    "CounterEvidence",
    "CreatorOverride",
    "CriterionKind",
    "CriterionSpec",
    "DisagreementReport",
    "EvidenceLinkError",
    "OverrideDeniedError",
    "RaterKind",
    "Rating",
    "RatingNotFoundError",
    "RubricAnalysis",
    "RubricDefinition",
    "RubricError",
    "RubricNotFoundError",
    "RubricService",
    "ScoreTrace",
    "UnexplainedScoreError",
    "default_criteria",
]
