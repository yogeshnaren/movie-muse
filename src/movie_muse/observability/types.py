"""Redacted traces, metrics, and SLO samples."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.schemas.api import dataclass_to_dict

REDACTION_MARK = "[REDACTED]"
FORBIDDEN_ATTRIBUTE_KEYS = frozenset(
    {
        "prompt",
        "screenplay",
        "dialogue",
        "password",
        "token",
        "secret",
        "body",
        "plaintext",
        "api_key",
        "authorization",
    }
)


@dataclass(frozen=True, slots=True)
class TraceRecord:
    id: str
    operation: str
    attributes: dict[str, Any]
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "operation": self.operation,
            "attributes": dict(self.attributes),
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceRecord:
        return cls(
            id=str(data["id"]),
            operation=str(data["operation"]),
            attributes=dict(data.get("attributes") or {}),
            recorded_at=str(data["recorded_at"]),
        )


@dataclass(frozen=True, slots=True)
class MetricSample:
    name: str
    value: float
    labels: dict[str, str]
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricSample:
        return cls(
            name=str(data["name"]),
            value=float(data["value"]),
            labels={str(key): str(value) for key, value in dict(data.get("labels") or {}).items()},
            recorded_at=str(data["recorded_at"]),
        )


@dataclass(frozen=True, slots=True)
class SloDefinition:
    name: str
    target: float
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)
