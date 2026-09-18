"""Typed failures for continuity analysis."""

from __future__ import annotations


class ContinuityError(RuntimeError):
    """Base class for continuity-analysis failures."""


class FindingNotFoundError(ContinuityError):
    """A resolve/suppress named a finding that is not in the index."""


class FindingClosedError(ContinuityError):
    """The finding is already resolved or suppressed."""


class HumanRequiredError(ContinuityError):
    """Resolve and suppress are human acts; integrations cannot close findings."""
