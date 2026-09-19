"""SBOM records, cost caps, and incident drills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.schemas.api import dataclass_to_dict

DENIED_PACKAGES = frozenset({"pycrypto", "pickle5"})


@dataclass(frozen=True, slots=True)
class SbomPackage:
    name: str
    version: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SbomPackage:
        return cls(name=str(data["name"]), version=str(data["version"]), source=str(data["source"]))


@dataclass(frozen=True, slots=True)
class Sbom:
    id: str
    packages: tuple[SbomPackage, ...]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "packages": [item.to_dict() for item in self.packages],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Sbom:
        return cls(
            id=str(data["id"]),
            packages=tuple(SbomPackage.from_dict(dict(item)) for item in data.get("packages", [])),
            created_at=str(data["created_at"]),
        )


@dataclass(frozen=True, slots=True)
class Incident:
    id: str
    title: str
    severity: str
    status: str
    backup_path: str | None
    independently_reproduced: bool
    created_at: str
    closed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Incident:
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            severity=str(data["severity"]),
            status=str(data["status"]),
            backup_path=str(data["backup_path"]) if data.get("backup_path") else None,
            independently_reproduced=bool(data.get("independently_reproduced", False)),
            created_at=str(data["created_at"]),
            closed_at=str(data["closed_at"]) if data.get("closed_at") else None,
        )
