"""Versioned mesh contracts, capabilities, vault credentials, and sync rows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

API_VERSION = "v1"
SUPPORTED_VERSIONS: tuple[str, ...] = ("v1",)
REVIEW_CONNECTOR_ENV = "MOVIE_MUSE_REVIEW_CONNECTOR_BASE_URL"
RATE_LIMIT_DEFAULT = 64
RATE_WINDOW_SECONDS = 60
TOKEN_PREFIX = "imt_"

CANON_FIELDS: tuple[str, ...] = (
    "screenplay",
    "revisions",
    "proposals",
    "approved_artifacts",
    "project_status",
)
EXTERNAL_FIELDS: tuple[str, ...] = (
    "payroll",
    "insurance_binding",
    "accounting",
)

OPENAPI_REQUIRED_PATHS: tuple[str, ...] = (
    "/v1/projects/{project_id}",
    "/v1/projects/{project_id}/revisions",
    "/v1/projects/{project_id}/proposals",
    "/v1/proposals/{proposal_id}/accept",
    "/v1/projects/{project_id}/artifacts",
    "/v1/status",
    "/v1/openapi.json",
    "/v1/capabilities",
)


class ToolSide(str, Enum):
    READ = "read"
    PROPOSE = "propose"
    COMMIT = "commit"


class SourceOfTruth(str, Enum):
    MOVIE_MUSE = "movie_muse"
    EXTERNAL_SPECIALIST = "external_specialist"


class CredentialStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


FIELD_SOURCE_OF_TRUTH: dict[str, SourceOfTruth] = {
    **{field: SourceOfTruth.MOVIE_MUSE for field in CANON_FIELDS},
    **{field: SourceOfTruth.EXTERNAL_SPECIALIST for field in EXTERNAL_FIELDS},
}


@dataclass(frozen=True, slots=True)
class MeshCapability:
    id: str
    name: str
    side: ToolSide
    scopes: tuple[str, ...]
    version: str = API_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "side": self.side.value,
            "scopes": list(self.scopes),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MeshCapability:
        scopes = data.get("scopes", ())
        if not isinstance(scopes, list | tuple):
            raise ValueError("capability scopes is not a list")
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            side=ToolSide(str(data["side"])),
            scopes=tuple(str(item) for item in scopes),
            version=str(data.get("version", API_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class VaultCredential:
    id: str
    actor_id: str
    project_id: str
    scopes: tuple[str, ...]
    status: CredentialStatus
    token_digest: str
    expires_at: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "project_id": self.project_id,
            "scopes": list(self.scopes),
            "status": self.status.value,
            "token_digest": self.token_digest,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VaultCredential:
        scopes = data.get("scopes", ())
        if not isinstance(scopes, list | tuple):
            raise ValueError("credential scopes is not a list")
        return cls(
            id=str(data["id"]),
            actor_id=str(data["actor_id"]),
            project_id=str(data["project_id"]),
            scopes=tuple(str(item) for item in scopes),
            status=CredentialStatus(str(data["status"])),
            token_digest=str(data["token_digest"]),
            expires_at=str(data["expires_at"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class IssuedToken:
    credential: VaultCredential
    token: str


@dataclass(frozen=True, slots=True)
class SyncRecord:
    id: str
    project_id: str
    capability_id: str
    payload_digest: str
    source: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "capability_id": self.capability_id,
            "payload_digest": self.payload_digest,
            "source": self.source,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncRecord:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            capability_id=str(data["capability_id"]),
            payload_digest=str(data["payload_digest"]),
            source=str(data["source"]),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class ProjectStatus:
    project_id: str
    title: str
    head_revision_id: str
    api_version: str
    proposal_count: int
    approved_artifact_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "head_revision_id": self.head_revision_id,
            "api_version": self.api_version,
            "proposal_count": self.proposal_count,
            "approved_artifact_count": self.approved_artifact_count,
        }
