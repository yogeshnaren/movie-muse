"""Typed failures for the state engine."""

from __future__ import annotations


class StateEngineError(RuntimeError):
    """Base class for state-engine failures."""


class UnknownSceneError(StateEngineError):
    """A temporal query named a scene that is not in FilmIR scene order."""


class UnknownSubjectError(StateEngineError):
    """A query or transition named a subject that is not in FilmIR."""


class AuthorityError(StateEngineError):
    """A correction or reduction violated epistemic authority rules."""
