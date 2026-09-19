"""Correspondence drafts, previews, and local delivery records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.artifacts.api import DeliveryRecord


@dataclass(frozen=True, slots=True)
class MessageDraft:
    id: str
    project_id: str
    artifact_id: str
    artifact_version_id: str
    channel: str
    recipients: tuple[str, ...]
    subject: str
    body: str
    created_at: str
    created_by_actor_id: str
    previewed: bool = False
    approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "artifact_id": self.artifact_id,
            "artifact_version_id": self.artifact_version_id,
            "channel": self.channel,
            "recipients": list(self.recipients),
            "subject": self.subject,
            "body": self.body,
            "created_at": self.created_at,
            "created_by_actor_id": self.created_by_actor_id,
            "previewed": self.previewed,
            "approved": self.approved,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MessageDraft:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            artifact_id=str(data["artifact_id"]),
            artifact_version_id=str(data["artifact_version_id"]),
            channel=str(data["channel"]),
            recipients=tuple(str(item) for item in data.get("recipients", ())),
            subject=str(data["subject"]),
            body=str(data["body"]),
            created_at=str(data["created_at"]),
            created_by_actor_id=str(data["created_by_actor_id"]),
            previewed=bool(data.get("previewed", False)),
            approved=bool(data.get("approved", False)),
        )


@dataclass(frozen=True, slots=True)
class MessagePreview:
    draft_id: str
    recipients: tuple[str, ...]
    subject: str
    body: str
    content: str
    render_id: str
    checksum: str
    channel: str


@dataclass(frozen=True, slots=True)
class SendResult:
    draft: MessageDraft
    delivery: DeliveryRecord
    network_sent: bool
