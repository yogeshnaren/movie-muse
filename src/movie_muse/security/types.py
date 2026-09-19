"""Threat findings, sealed blobs, and classification ranks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import dataclass_to_dict

CLASSIFICATION_RANKS: dict[str, int] = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
}
REMOTE_MAX = "internal"


class FindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class ThreatFinding:
    id: str
    title: str
    severity: FindingSeverity
    status: FindingStatus
    asset: str
    created_at: str
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = dataclass_to_dict(self)
        payload["severity"] = self.severity.value
        payload["status"] = self.status.value
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThreatFinding:
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            severity=FindingSeverity(str(data["severity"])),
            status=FindingStatus(str(data["status"])),
            asset=str(data["asset"]),
            created_at=str(data["created_at"]),
            resolved_at=str(data["resolved_at"]) if data.get("resolved_at") else None,
        )


@dataclass(frozen=True, slots=True)
class SealedBlob:
    nonce: str
    ciphertext: str
    mac: str
    byok: bool

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SealedBlob:
        return cls(
            nonce=str(data["nonce"]),
            ciphertext=str(data["ciphertext"]),
            mac=str(data["mac"]),
            byok=bool(data.get("byok", False)),
        )
