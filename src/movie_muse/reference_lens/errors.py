"""Typed failures for the Reference Lens."""

from __future__ import annotations


class ReferenceLensError(RuntimeError):
    """Base class for Reference Lens failures."""


class LensDisabledError(ReferenceLensError):
    """The writer disabled the Reference Lens for this project."""


class TrainingMemoryClaimError(ReferenceLensError):
    """The lens refuses unverifiable model-training-memory retrieval."""


class CitationUnresolvedError(ReferenceLensError):
    """A surfaced citation could not be resolved in the rights registry."""
