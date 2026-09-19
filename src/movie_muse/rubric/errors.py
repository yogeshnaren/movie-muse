"""Typed failures for evidence-linked rubric analysis."""

from __future__ import annotations


class RubricError(RuntimeError):
    """Base class for rubric analysis failures."""


class RubricNotFoundError(RubricError):
    """The named rubric definition is not in the index."""


class AnalysisNotFoundError(RubricError):
    """The named analysis is not in the index."""


class RatingNotFoundError(RubricError):
    """The named rating is not in the index."""


class UnexplainedScoreError(RubricError):
    """Every score must cite evidence refs and a rationale."""


class EvidenceLinkError(RubricError):
    """Evidence refs must point at FilmIR entities, scenes, blocks, or intents."""


class OverrideDeniedError(RubricError):
    """Creator overrides require a human ACCEPT and never delete prior ratings."""


class CalibrationError(RubricError):
    """Calibration residuals are advisory comparisons, not canon scores."""


class AdvisoryLabelError(RubricError):
    """Exported analysis must stay labeled advisory and must not claim canon."""
