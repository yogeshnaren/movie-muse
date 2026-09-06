"""Fail-closed errors for deterministic layout."""

from __future__ import annotations


class LayoutError(RuntimeError):
    """Base class for layout engine failures."""


class LockedPaginationError(LayoutError):
    """Pagination would move locked pages/scenes without an explicit unlock."""


class UnknownProfileError(LayoutError):
    """A style or paper profile id is not in the pinned catalog."""


class LayoutEngineError(LayoutError):
    """The engine cannot produce a layout for the given inputs."""
