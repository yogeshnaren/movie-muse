"""Public surface of ``movie_muse.creative_intent``.

Hosts and other modules must import this module, never sibling internals.
Direct manipulation and chat write the same typed ``IntentCommand``.
"""

from __future__ import annotations

from movie_muse.creative_intent.errors import (
    CreativeIntentError,
    IntentLockError,
    IntentMergeConflictError,
    IntentScopeError,
    StaleIntentError,
    UnknownIntentError,
)
from movie_muse.creative_intent.service import CreativeIntentService
from movie_muse.creative_intent.types import (
    IntentAction,
    IntentCommand,
    IntentConflict,
    IntentEnvelope,
    IntentKind,
    IntentMergeResult,
    IntentOrigin,
    IntentRecord,
    intent_key,
)
from movie_muse.schemas.api import CreativeIntentIR, IntentScope, IntentSourceRole

__all__ = [
    "CreativeIntentError",
    "CreativeIntentIR",
    "CreativeIntentService",
    "IntentAction",
    "IntentCommand",
    "IntentConflict",
    "IntentEnvelope",
    "IntentKind",
    "IntentLockError",
    "IntentMergeConflictError",
    "IntentMergeResult",
    "IntentOrigin",
    "IntentRecord",
    "IntentScope",
    "IntentScopeError",
    "IntentSourceRole",
    "StaleIntentError",
    "UnknownIntentError",
    "intent_key",
]
