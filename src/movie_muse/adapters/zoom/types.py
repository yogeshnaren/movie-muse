"""OAuth credentials, least scopes, and signed Zoom webhook envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

ZOOM_SANDBOX_ENV = "MOVIE_MUSE_ZOOM_SANDBOX_BASE_URL"
ZOOM_AUTHORIZE_URL = "https://zoom.us/oauth/authorize"
LEAST_SCOPES = ("meeting:read", "recording:read")
SIGNATURE_HEADER = "X-Zm-Signature"
TIMESTAMP_HEADER = "X-Zm-Request-Timestamp"
REPLAY_WINDOW_SECONDS = 300


class CredentialStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class ZoomCredential:
    id: str
    project_id: str
    actor_id: str
    scopes: tuple[str, ...]
    status: CredentialStatus
    expires_at: str
    token_digest: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "actor_id": self.actor_id,
            "scopes": list(self.scopes),
            "status": self.status.value,
            "expires_at": self.expires_at,
            "token_digest": self.token_digest,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ZoomCredential:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            actor_id=str(data["actor_id"]),
            scopes=tuple(str(item) for item in data.get("scopes", ())),
            status=CredentialStatus(str(data["status"])),
            expires_at=str(data["expires_at"]),
            token_digest=str(data["token_digest"]),
            created_at=str(data["created_at"]),
        )
