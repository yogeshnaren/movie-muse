"""Public surface of ``movie_muse.visual_language``.

Hosts and other modules must import this module, never sibling internals.
Palette correlations are not claimed as causation. ShotIR updates are proposals.
"""

from __future__ import annotations

from movie_muse.visual_language.errors import (
    CausationClaimError,
    LanguageNotFoundError,
    SafetyReviewError,
    ShotProposalError,
    UncitedReferenceError,
    VisualLanguageError,
)
from movie_muse.visual_language.service import VisualLanguageService
from movie_muse.visual_language.types import (
    DISCLAIMER,
    FORBIDDEN_CAUSATION_PHRASES,
    EvolutionStep,
    LanguageRule,
    PaletteSwatch,
    RuleKind,
    SafetyReview,
    ShotColorProposal,
    VisualLanguage,
)

__all__ = [
    "DISCLAIMER",
    "FORBIDDEN_CAUSATION_PHRASES",
    "CausationClaimError",
    "EvolutionStep",
    "LanguageNotFoundError",
    "LanguageRule",
    "PaletteSwatch",
    "RuleKind",
    "SafetyReview",
    "SafetyReviewError",
    "ShotColorProposal",
    "ShotProposalError",
    "UncitedReferenceError",
    "VisualLanguage",
    "VisualLanguageError",
    "VisualLanguageService",
]
