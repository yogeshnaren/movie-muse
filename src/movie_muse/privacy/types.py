"""Training policy, residency, and erasure records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import dataclass_to_dict

NO_TRAINING_DEFAULT = True
PROVIDER_RETENTION = "minimum"
CROSS_USER_PROMPT_CACHE = False


class Residency(str, Enum):
    US = "us"
    EU = "eu"
    PRIVATE_ROUTE = "private_route"


@dataclass(frozen=True, slots=True)
class TrainingPolicy:
    no_training_default: bool = NO_TRAINING_DEFAULT
    opt_in: bool = False
    provider_retention: str = PROVIDER_RETENTION
    cross_user_prompt_cache: bool = CROSS_USER_PROMPT_CACHE

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class ErasureRecord:
    id: str
    subject_id: str
    erased_at: str
    retain_until: str

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ErasureRecord:
        return cls(
            id=str(data["id"]),
            subject_id=str(data["subject_id"]),
            erased_at=str(data["erased_at"]),
            retain_until=str(data["retain_until"]),
        )


@dataclass(frozen=True, slots=True)
class SubjectExport:
    subject_id: str
    payload: dict[str, Any]
    residency: str
    training_opt_in: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "payload": dict(self.payload),
            "residency": self.residency,
            "training_opt_in": self.training_opt_in,
        }
