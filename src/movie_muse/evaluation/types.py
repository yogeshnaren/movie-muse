"""Evaluation runs, correction burden, and Creator Leverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.schemas.api import dataclass_to_dict

QUALITY_BASELINE = 0.7
SAFETY_BASELINE = 1.0
FORBIDDEN_POPULATION_PHRASES = (
    "human sample",
    "human samples",
    "bootstrap population",
    "demographic population",
    "population estimate",
)


@dataclass(frozen=True, slots=True)
class EvalRun:
    id: str
    task_id: str
    route_kind: str
    provider: str
    quality: float
    safety: float
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalRun:
        return cls(
            id=str(data["id"]),
            task_id=str(data["task_id"]),
            route_kind=str(data["route_kind"]),
            provider=str(data["provider"]),
            quality=float(data["quality"]),
            safety=float(data["safety"]),
            recorded_at=str(data["recorded_at"]),
        )


@dataclass(frozen=True, slots=True)
class CorrectionBurden:
    regenerations: int
    accepted: int
    correction_minutes: float
    ratio: float

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class CreatorLeverage:
    useful_minutes_removed: float
    correction_minutes: float
    verification_minutes: float
    ratio: float

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)
