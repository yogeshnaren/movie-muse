"""Typed failures for Room Mode."""

from __future__ import annotations


class RoomModeError(RuntimeError):
    """Base class for Room Mode failures."""


class RoomNotFoundError(RoomModeError):
    """The named room session is not in the index."""


class RoomClosedError(RoomModeError):
    """The room session is closed and no longer accepts capture."""


class FakeHumanError(RoomModeError):
    """Simulated seats must not be presented as human participants."""


class HarvestRequiresReviewError(RoomModeError):
    """Room Harvest cannot auto-promote; explicit review is required."""


class SoloAdmissionError(RoomModeError):
    """A solo room already has its human facilitator."""


class UnknownParticipantError(RoomModeError):
    """The named participant is not in this room."""


class HarvestNotOpenError(RoomModeError):
    """Promote/discard through harvest requires an open harvest review."""
