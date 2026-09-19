"""Typed failures for ShotIR."""

from __future__ import annotations


class ShotIRError(RuntimeError):
    """Base class for ShotIR failures."""


class ShotNotFoundError(ShotIRError):
    """The named shot is not in the index."""


class LockedAttributeError(ShotIRError):
    """A locked camera or composition attribute cannot change without unlock."""


class ProviderIndependentError(ShotIRError):
    """ShotIR cannot be defined by an image or video provider."""
