"""Typed failures for production breakdown."""

from __future__ import annotations


class BreakdownError(RuntimeError):
    """Base class for breakdown failures."""


class UnlockedSourceError(BreakdownError):
    """Derivation requires a locked source revision."""


class BreakdownNotFoundError(BreakdownError):
    """The named breakdown projection is not in the index."""


class ElementNotFoundError(BreakdownError):
    """The named breakdown element is not on the projection."""


class UnverifiedEditError(BreakdownError):
    """Human verification is required before the breakdown is complete."""


class StaleBreakdownError(BreakdownError):
    """The breakdown is labeled stale and is not current."""


class ProposalRequiredError(BreakdownError):
    """Breakdown edits must go through an inspectable ChangeSet proposal."""
