"""Typed failures for visual language and color intelligence."""

from __future__ import annotations


class VisualLanguageError(RuntimeError):
    """Base class for visual-language failures."""


class LanguageNotFoundError(VisualLanguageError):
    """The named visual language is not in the index."""


class UncitedReferenceError(VisualLanguageError):
    """A reference must be a permitted, cited rights source."""


class CausationClaimError(VisualLanguageError):
    """Palette correlations are not claimed as causation."""


class SafetyReviewError(VisualLanguageError):
    """Skin-tone and accessibility review must pass before ShotIR proposals."""


class ShotProposalError(VisualLanguageError):
    """ShotIR color updates require a human-accepted visual-language proposal."""
