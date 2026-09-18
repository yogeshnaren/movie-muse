"""Room sessions, participants, boards, votes, and harvest items."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RoomKind(str, Enum):
    SOLO = "solo"
    MULTI_WRITER = "multi_writer"


class RoomTeamMode(str, Enum):
    WRITER = "writer"
    RESEARCH_TEAM = "research_team"


class RoomStatus(str, Enum):
    OPEN = "open"
    HARVESTING = "harvesting"
    CLOSED = "closed"


class ParticipantKind(str, Enum):
    HUMAN = "human"
    SIMULATED = "simulated"


class RoomRole(str, Enum):
    FACILITATOR = "facilitator"
    WRITER = "writer"
    RESEARCHER = "researcher"


class VoteValue(str, Enum):
    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"


class HarvestItemState(str, Enum):
    CAPTURED = "captured"
    UNDER_REVIEW = "under_review"
    PROMOTED = "promoted"
    DISCARDED = "discarded"


@dataclass(frozen=True, slots=True)
class RoomParticipant:
    id: str
    display_name: str
    kind: ParticipantKind
    role: RoomRole
    presented_as_human: bool
    actor_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "kind": self.kind.value,
            "role": self.role.value,
            "presented_as_human": self.presented_as_human,
            "actor_id": self.actor_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomParticipant:
        return cls(
            id=str(data["id"]),
            display_name=str(data["display_name"]),
            kind=ParticipantKind(str(data["kind"])),
            role=RoomRole(str(data["role"])),
            presented_as_human=bool(data["presented_as_human"]),
            actor_id=str(data["actor_id"]) if data.get("actor_id") else None,
        )


@dataclass(frozen=True, slots=True)
class BoardCard:
    id: str
    room_id: str
    text: str
    author_participant_id: str
    column: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "text": self.text,
            "author_participant_id": self.author_participant_id,
            "column": self.column,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BoardCard:
        return cls(
            id=str(data["id"]),
            room_id=str(data["room_id"]),
            text=str(data["text"]),
            author_participant_id=str(data["author_participant_id"]),
            column=str(data["column"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class RoomVote:
    id: str
    room_id: str
    target_id: str
    actor_id: str
    value: VoteValue
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "target_id": self.target_id,
            "actor_id": self.actor_id,
            "value": self.value.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomVote:
        return cls(
            id=str(data["id"]),
            room_id=str(data["room_id"]),
            target_id=str(data["target_id"]),
            actor_id=str(data["actor_id"]),
            value=VoteValue(str(data["value"])),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class RoomAck:
    id: str
    room_id: str
    target_id: str
    actor_id: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "target_id": self.target_id,
            "actor_id": self.actor_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomAck:
        return cls(
            id=str(data["id"]),
            room_id=str(data["room_id"]),
            target_id=str(data["target_id"]),
            actor_id=str(data["actor_id"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class HarvestItem:
    event_id: str
    candidate_id: str
    state: HarvestItemState

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "candidate_id": self.candidate_id,
            "state": self.state.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HarvestItem:
        return cls(
            event_id=str(data["event_id"]),
            candidate_id=str(data["candidate_id"]),
            state=HarvestItemState(str(data["state"])),
        )


@dataclass(frozen=True, slots=True)
class RoomTimer:
    duration_seconds: int
    started_at: str
    ends_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at,
            "ends_at": self.ends_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomTimer:
        return cls(
            duration_seconds=int(data["duration_seconds"]),
            started_at=str(data["started_at"]),
            ends_at=str(data["ends_at"]),
        )


@dataclass(frozen=True, slots=True)
class RoomSession:
    id: str
    project_id: str
    branch_id: str
    revision_id: str
    kind: RoomKind
    team_mode: RoomTeamMode
    status: RoomStatus
    facilitator_actor_id: str
    started_at: str
    participants: tuple[RoomParticipant, ...]
    ended_at: str | None = None
    timer: RoomTimer | None = None
    proposal_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "branch_id": self.branch_id,
            "revision_id": self.revision_id,
            "kind": self.kind.value,
            "team_mode": self.team_mode.value,
            "status": self.status.value,
            "facilitator_actor_id": self.facilitator_actor_id,
            "started_at": self.started_at,
            "participants": [item.to_dict() for item in self.participants],
            "ended_at": self.ended_at,
            "timer": self.timer.to_dict() if self.timer else None,
            "proposal_ids": list(self.proposal_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoomSession:
        timer_raw = data.get("timer")
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            branch_id=str(data["branch_id"]),
            revision_id=str(data["revision_id"]),
            kind=RoomKind(str(data["kind"])),
            team_mode=RoomTeamMode(str(data["team_mode"])),
            status=RoomStatus(str(data["status"])),
            facilitator_actor_id=str(data["facilitator_actor_id"]),
            started_at=str(data["started_at"]),
            participants=tuple(
                RoomParticipant.from_dict(item) for item in data.get("participants", ())
            ),
            ended_at=str(data["ended_at"]) if data.get("ended_at") else None,
            timer=RoomTimer.from_dict(timer_raw) if timer_raw else None,
            proposal_ids=tuple(str(item) for item in data.get("proposal_ids", ())),
        )
