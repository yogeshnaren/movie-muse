"""Typed failures for context assembly."""

from __future__ import annotations


class ContextError(RuntimeError):
    """Base class for fail-closed context errors."""


class TenantIsolationError(ContextError):
    """Assembly mixed projects or workspaces."""


class BranchIsolationError(ContextError):
    """Assembly mixed branches or used a foreign branch head."""


class StaleCanonError(ContextError):
    """Expected revision or bound state does not match the live branch head."""


class ContextBudgetExceededError(ContextError):
    """The model-independent budget cannot hold required citation-bearing segments."""
