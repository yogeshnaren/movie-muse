"""Typed failures for the scheduling constraint engine."""

from __future__ import annotations


class SchedulingError(RuntimeError):
    """Base class for scheduling failures."""


class ScheduleNotFoundError(SchedulingError):
    """The named schedule is not in the index."""


class StaleScheduleError(SchedulingError):
    """A stale schedule cannot be treated as current."""


class InfeasibleScheduleError(SchedulingError):
    """A hard constraint would be silently broken; the edit is refused."""

    def __init__(self, message: str, explanations: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.explanations = explanations


class StripNotFoundError(SchedulingError):
    """The named strip or scene is not on the schedule."""
