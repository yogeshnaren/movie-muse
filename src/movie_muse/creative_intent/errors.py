"""Typed failures for creator intent."""

from __future__ import annotations


class CreativeIntentError(RuntimeError):
    """Base class for CreativeIntentIR failures."""


class StaleIntentError(CreativeIntentError):
    """Apply/rebind named a revision that is not the branch head."""


class IntentLockError(CreativeIntentError):
    """A locked or inferred intent violated lock/ownership rules."""


class IntentMergeConflictError(CreativeIntentError):
    """Branch merge found overlapping intent keys with different statements."""


class UnknownIntentError(CreativeIntentError):
    """Named intent id is not in the workspace index."""


class IntentScopeError(CreativeIntentError):
    """Scope target is not valid for the declared FilmIR/document scope."""
