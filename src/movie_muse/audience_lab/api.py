"""Public surface of ``movie_muse.audience_lab``.

Hosts and other modules must import this module, never sibling internals.
Synthetic LLM personas are hypotheses, never human or bootstrap samples.
"""

from __future__ import annotations

from movie_muse.audience_lab.errors import (
    AudienceLabError,
    ConsentRequiredError,
    HumanProvenanceError,
    InsufficientCalibrationError,
    PopulationClaimError,
    RunNotFoundError,
)
from movie_muse.audience_lab.service import AudienceLabService, assert_no_population_claim
from movie_muse.audience_lab.types import (
    DISCLAIMER,
    FORBIDDEN_POPULATION_PHRASES,
    HUMAN_TIERS,
    NON_INDEPENDENCE_NOTICE,
    AudienceSample,
    CalibrationReport,
    ConsentRecord,
    ConsentState,
    EvidenceTier,
    IntendedEffectComparison,
    LabRun,
    SegmentHypothesis,
)

__all__ = [
    "DISCLAIMER",
    "FORBIDDEN_POPULATION_PHRASES",
    "HUMAN_TIERS",
    "NON_INDEPENDENCE_NOTICE",
    "AudienceLabError",
    "AudienceLabService",
    "AudienceSample",
    "CalibrationReport",
    "ConsentRecord",
    "ConsentRequiredError",
    "ConsentState",
    "EvidenceTier",
    "HumanProvenanceError",
    "InsufficientCalibrationError",
    "IntendedEffectComparison",
    "LabRun",
    "PopulationClaimError",
    "RunNotFoundError",
    "SegmentHypothesis",
    "assert_no_population_claim",
]
