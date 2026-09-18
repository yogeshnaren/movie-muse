"""Meeting sessions, consent, utterances, media links, and harvest items."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConsentState(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"


class CaptureState(str, Enum):
    CONSENT_REQUIRED = "consent_required"
    RECORDING = "recording"
    STOPPED = "stopped"
    IMPORTED = "imported"
    DELETED = "deleted"


class HarvestItemState(str, Enum):
    CAPTURED = "captured"
    UNDER_REVIEW = "under_review"
    PROMOTED = "promoted"
    DISCARDED = "discarded"


@dataclass(frozen=True, slots=True)
class ProvenanceEntry:
    actor_id: str
    operation: str
    created_at: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "operation": self.operation,
            "created_at": self.created_at,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProvenanceEntry:
        return cls(
            actor_id=str(data["actor_id"]),
            operation=str(data["operation"]),
            created_at=str(data["created_at"]),
            note=str(data.get("note", "")),
        )


@dataclass(frozen=True, slots=True)
class Utterance:
    id: str
    speaker_label: str
    start_ms: int
    end_ms: int
    text: str
    speaker_actor_id: str | None = None
    provenance: tuple[ProvenanceEntry, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "speaker_label": self.speaker_label,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
            "speaker_actor_id": self.speaker_actor_id,
            "provenance": [item.to_dict() for item in self.provenance],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Utterance:
        return cls(
            id=str(data["id"]),
            speaker_label=str(data["speaker_label"]),
            start_ms=int(data["start_ms"]),
            end_ms=int(data["end_ms"]),
            text=str(data["text"]),
            speaker_actor_id=(
                str(data["speaker_actor_id"]) if data.get("speaker_actor_id") else None
            ),
            provenance=tuple(
                ProvenanceEntry.from_dict(item) for item in data.get("provenance", ())
            ),
        )


@dataclass(frozen=True, slots=True)
class MediaLink:
    id: str
    title: str
    uri: str
    start_ms: int
    artifact_id: str | None = None
    utterance_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "uri": self.uri,
            "start_ms": self.start_ms,
            "artifact_id": self.artifact_id,
            "utterance_id": self.utterance_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MediaLink:
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            uri=str(data["uri"]),
            start_ms=int(data["start_ms"]),
            artifact_id=str(data["artifact_id"]) if data.get("artifact_id") else None,
            utterance_id=str(data["utterance_id"]) if data.get("utterance_id") else None,
        )


@dataclass(frozen=True, slots=True)
class ConsentView:
    meeting_id: str
    consent_state: ConsentState
    capture_state: CaptureState
    visible: bool
    actor_id: str | None = None
    decided_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "consent_state": self.consent_state.value,
            "capture_state": self.capture_state.value,
            "visible": self.visible,
            "actor_id": self.actor_id,
            "decided_at": self.decided_at,
        }


@dataclass(frozen=True, slots=True)
class HarvestItem:
    candidate_id: str
    state: HarvestItemState
    utterance_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "state": self.state.value,
            "utterance_id": self.utterance_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HarvestItem:
        return cls(
            candidate_id=str(data["candidate_id"]),
            state=HarvestItemState(str(data["state"])),
            utterance_id=str(data["utterance_id"]) if data.get("utterance_id") else None,
        )


@dataclass(frozen=True, slots=True)
class MeetingSession:
    id: str
    project_id: str
    branch_id: str
    revision_id: str
    consent_state: ConsentState
    capture_state: CaptureState
    created_at: str
    created_by_actor_id: str
    room_id: str | None = None
    consent_actor_id: str | None = None
    consent_at: str | None = None
    artifact_id: str | None = None
    artifact_version_id: str | None = None
    retention_until: str | None = None
    utterances: tuple[Utterance, ...] = ()
    media_links: tuple[MediaLink, ...] = ()
    harvest: tuple[HarvestItem, ...] = ()
    harvest_open: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "branch_id": self.branch_id,
            "revision_id": self.revision_id,
            "consent_state": self.consent_state.value,
            "capture_state": self.capture_state.value,
            "created_at": self.created_at,
            "created_by_actor_id": self.created_by_actor_id,
            "room_id": self.room_id,
            "consent_actor_id": self.consent_actor_id,
            "consent_at": self.consent_at,
            "artifact_id": self.artifact_id,
            "artifact_version_id": self.artifact_version_id,
            "retention_until": self.retention_until,
            "utterances": [item.to_dict() for item in self.utterances],
            "media_links": [item.to_dict() for item in self.media_links],
            "harvest": [item.to_dict() for item in self.harvest],
            "harvest_open": self.harvest_open,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MeetingSession:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            branch_id=str(data["branch_id"]),
            revision_id=str(data["revision_id"]),
            consent_state=ConsentState(str(data["consent_state"])),
            capture_state=CaptureState(str(data["capture_state"])),
            created_at=str(data["created_at"]),
            created_by_actor_id=str(data["created_by_actor_id"]),
            room_id=str(data["room_id"]) if data.get("room_id") else None,
            consent_actor_id=(
                str(data["consent_actor_id"]) if data.get("consent_actor_id") else None
            ),
            consent_at=str(data["consent_at"]) if data.get("consent_at") else None,
            artifact_id=str(data["artifact_id"]) if data.get("artifact_id") else None,
            artifact_version_id=(
                str(data["artifact_version_id"]) if data.get("artifact_version_id") else None
            ),
            retention_until=(
                str(data["retention_until"]) if data.get("retention_until") else None
            ),
            utterances=tuple(Utterance.from_dict(item) for item in data.get("utterances", ())),
            media_links=tuple(
                MediaLink.from_dict(item) for item in data.get("media_links", ())
            ),
            harvest=tuple(HarvestItem.from_dict(item) for item in data.get("harvest", ())),
            harvest_open=bool(data.get("harvest_open", False)),
        )
