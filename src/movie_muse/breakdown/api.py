"""Public surface of ``movie_muse.breakdown``.

Hosts and other modules must import this module, never sibling internals.
Derive from locked source revisions. Edits create inspectable ChangeSets.
Human verification is required before completeness thresholds pass.
"""

from __future__ import annotations

from movie_muse.breakdown.errors import (
    BreakdownError,
    BreakdownNotFoundError,
    ElementNotFoundError,
    ProposalRequiredError,
    StaleBreakdownError,
    UnlockedSourceError,
    UnverifiedEditError,
)
from movie_muse.breakdown.service import BreakdownService
from movie_muse.breakdown.thresholds import DECLARED_THRESHOLDS
from movie_muse.breakdown.types import (
    BreakdownElement,
    CompletenessReport,
    ElementKind,
    PendingEdit,
    ScreenplayEvidence,
    StoredBreakdown,
    VerificationState,
)

__all__ = [
    "DECLARED_THRESHOLDS",
    "BreakdownElement",
    "BreakdownError",
    "BreakdownNotFoundError",
    "BreakdownService",
    "CompletenessReport",
    "ElementKind",
    "ElementNotFoundError",
    "PendingEdit",
    "ProposalRequiredError",
    "ScreenplayEvidence",
    "StaleBreakdownError",
    "StoredBreakdown",
    "UnlockedSourceError",
    "UnverifiedEditError",
    "VerificationState",
]
