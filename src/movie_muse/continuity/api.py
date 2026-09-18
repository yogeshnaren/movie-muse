"""Public surface of ``movie_muse.continuity``.

Hosts and other modules must import this module, never sibling internals.
Analysis is deterministic and does not call ModelRouter.
"""

from __future__ import annotations

from movie_muse.continuity.errors import (
    ContinuityError,
    FindingClosedError,
    FindingNotFoundError,
    HumanRequiredError,
)
from movie_muse.continuity.service import ContinuityService
from movie_muse.continuity.thresholds import DECLARED_THRESHOLDS
from movie_muse.continuity.types import (
    AUTHOR_MODES,
    BASE_MATERIALITY,
    LOGISTICS_DIMENSIONS,
    PRODUCTION_MODES,
    ContinuityFinding,
    ContinuityReport,
    FindingCategory,
    FindingDisposition,
    FindingStatus,
    Materiality,
    category_for,
    materiality_for,
)

__all__ = [
    "AUTHOR_MODES",
    "BASE_MATERIALITY",
    "DECLARED_THRESHOLDS",
    "LOGISTICS_DIMENSIONS",
    "PRODUCTION_MODES",
    "ContinuityError",
    "ContinuityFinding",
    "ContinuityReport",
    "ContinuityService",
    "FindingCategory",
    "FindingClosedError",
    "FindingDisposition",
    "FindingNotFoundError",
    "FindingStatus",
    "HumanRequiredError",
    "Materiality",
    "category_for",
    "materiality_for",
]
