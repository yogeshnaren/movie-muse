"""Public surface of ``movie_muse.state_engine``.

Hosts and other modules must import this module, never sibling internals.
The reducer is deterministic and does not call ModelRouter.
"""

from __future__ import annotations

from movie_muse.state_engine.errors import (
    AuthorityError,
    StateEngineError,
    UnknownSceneError,
    UnknownSubjectError,
)
from movie_muse.state_engine.extract import (
    extract_structural_transitions,
    transitions_from_inferred,
)
from movie_muse.state_engine.reduce import facts_at_scene, reduce_transitions
from movie_muse.state_engine.service import StateEngine
from movie_muse.state_engine.thresholds import DECLARED_THRESHOLDS
from movie_muse.state_engine.types import (
    AUTHORITY_RANK,
    Contradiction,
    HumanCorrection,
    Polarity,
    Reduction,
    StateDimension,
    StateFact,
    StateSnapshot,
    StateTransition,
)

__all__ = [
    "AUTHORITY_RANK",
    "DECLARED_THRESHOLDS",
    "AuthorityError",
    "Contradiction",
    "HumanCorrection",
    "Polarity",
    "Reduction",
    "StateDimension",
    "StateEngine",
    "StateEngineError",
    "StateFact",
    "StateSnapshot",
    "StateTransition",
    "UnknownSceneError",
    "UnknownSubjectError",
    "extract_structural_transitions",
    "facts_at_scene",
    "reduce_transitions",
    "transitions_from_inferred",
]
