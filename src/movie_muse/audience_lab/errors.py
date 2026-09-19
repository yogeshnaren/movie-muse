"""Typed failures for evidence-tiered audience resonance."""

from __future__ import annotations


class AudienceLabError(RuntimeError):
    """Base class for audience lab failures."""


class RunNotFoundError(AudienceLabError):
    """The named lab run is not in the index."""


class ConsentRequiredError(AudienceLabError):
    """Human audience data requires visible granted consent."""


class PopulationClaimError(AudienceLabError):
    """Synthetic personas must not be described as human or bootstrap samples."""


class InsufficientCalibrationError(AudienceLabError):
    """Calibration requires a human evidence tier; residuals are not population estimates."""


class HumanProvenanceError(AudienceLabError):
    """Human data requires a permitted rights source and provenance."""
