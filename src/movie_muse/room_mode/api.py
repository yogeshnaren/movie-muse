"""Public surface of ``movie_muse.room_mode``.

Hosts and other modules must import this module, never sibling internals.
Simulated seats are never presented as human participants. Room Harvest
never auto-promotes candidates.
"""

from __future__ import annotations

from movie_muse.room_mode.errors import (
    FakeHumanError,
    HarvestNotOpenError,
    HarvestRequiresReviewError,
    RoomClosedError,
    RoomModeError,
    RoomNotFoundError,
    SoloAdmissionError,
    UnknownParticipantError,
)
from movie_muse.room_mode.service import RoomModeService
from movie_muse.room_mode.types import (
    BoardCard,
    HarvestItem,
    HarvestItemState,
    ParticipantKind,
    RoomAck,
    RoomKind,
    RoomParticipant,
    RoomRole,
    RoomSession,
    RoomStatus,
    RoomTeamMode,
    RoomTimer,
    RoomVote,
    VoteValue,
)

__all__ = [
    "BoardCard",
    "FakeHumanError",
    "HarvestItem",
    "HarvestItemState",
    "HarvestNotOpenError",
    "HarvestRequiresReviewError",
    "ParticipantKind",
    "RoomAck",
    "RoomClosedError",
    "RoomKind",
    "RoomModeError",
    "RoomModeService",
    "RoomNotFoundError",
    "RoomParticipant",
    "RoomRole",
    "RoomSession",
    "RoomStatus",
    "RoomTeamMode",
    "RoomTimer",
    "RoomVote",
    "SoloAdmissionError",
    "UnknownParticipantError",
    "VoteValue",
]
