"""Boards, strips, pins, availability, and explainable schedule conflicts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import ProductionProjection


class DayPart(str, Enum):
    DAY = "day"
    NIGHT = "night"
    UNKNOWN = "unknown"


class ConstraintSeverity(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class ResourceKind(str, Enum):
    CAST = "cast"
    LOCATION = "location"


@dataclass(frozen=True, slots=True)
class SceneDemand:
    scene_id: str
    location: str
    day_part: DayPart
    cast: tuple[str, ...]
    duration_minutes: int
    has_stunt: bool
    has_minor: bool
    heading: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "location": self.location,
            "day_part": self.day_part.value,
            "cast": list(self.cast),
            "duration_minutes": self.duration_minutes,
            "has_stunt": self.has_stunt,
            "has_minor": self.has_minor,
            "heading": self.heading,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SceneDemand:
        return cls(
            scene_id=str(data["scene_id"]),
            location=str(data["location"]),
            day_part=DayPart(str(data["day_part"])),
            cast=tuple(str(item) for item in data.get("cast", ())),
            duration_minutes=int(data["duration_minutes"]),
            has_stunt=bool(data.get("has_stunt", False)),
            has_minor=bool(data.get("has_minor", False)),
            heading=str(data.get("heading", "")),
        )


@dataclass(frozen=True, slots=True)
class Strip:
    id: str
    board_index: int
    order: int
    scene: SceneDemand
    used_minutes: int
    company_move_minutes: int
    pinned: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "board_index": self.board_index,
            "order": self.order,
            "scene": self.scene.to_dict(),
            "used_minutes": self.used_minutes,
            "company_move_minutes": self.company_move_minutes,
            "pinned": self.pinned,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Strip:
        return cls(
            id=str(data["id"]),
            board_index=int(data["board_index"]),
            order=int(data["order"]),
            scene=SceneDemand.from_dict(data["scene"]),
            used_minutes=int(data["used_minutes"]),
            company_move_minutes=int(data.get("company_move_minutes", 0)),
            pinned=bool(data.get("pinned", False)),
        )


@dataclass(frozen=True, slots=True)
class Board:
    id: str
    index: int
    strips: tuple[Strip, ...]
    used_minutes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "strips": [item.to_dict() for item in self.strips],
            "used_minutes": self.used_minutes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Board:
        return cls(
            id=str(data["id"]),
            index=int(data["index"]),
            strips=tuple(Strip.from_dict(item) for item in data.get("strips", ())),
            used_minutes=int(data.get("used_minutes", 0)),
        )


@dataclass(frozen=True, slots=True)
class Pin:
    scene_id: str
    board_index: int

    def to_dict(self) -> dict[str, Any]:
        return {"scene_id": self.scene_id, "board_index": self.board_index}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pin:
        return cls(scene_id=str(data["scene_id"]), board_index=int(data["board_index"]))


@dataclass(frozen=True, slots=True)
class AvailabilityBlock:
    kind: ResourceKind
    name: str
    board_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "name": self.name,
            "board_index": self.board_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AvailabilityBlock:
        return cls(
            kind=ResourceKind(str(data["kind"])),
            name=str(data["name"]),
            board_index=int(data["board_index"]),
        )


@dataclass(frozen=True, slots=True)
class Conflict:
    severity: ConstraintSeverity
    code: str
    scene_ids: tuple[str, ...]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "scene_ids": list(self.scene_ids),
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Conflict:
        return cls(
            severity=ConstraintSeverity(str(data["severity"])),
            code=str(data["code"]),
            scene_ids=tuple(str(item) for item in data.get("scene_ids", ())),
            explanation=str(data["explanation"]),
        )


@dataclass(frozen=True, slots=True)
class ScheduleScenario:
    id: str
    seed: int
    boards: tuple[Board, ...]
    infeasible: tuple[Conflict, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "seed": self.seed,
            "boards": [item.to_dict() for item in self.boards],
            "infeasible": [item.to_dict() for item in self.infeasible],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduleScenario:
        return cls(
            id=str(data["id"]),
            seed=int(data["seed"]),
            boards=tuple(Board.from_dict(item) for item in data.get("boards", ())),
            infeasible=tuple(Conflict.from_dict(item) for item in data.get("infeasible", ())),
        )


@dataclass(frozen=True, slots=True)
class StoredSchedule:
    projection: ProductionProjection
    breakdown_id: str
    seed: int
    boards: tuple[Board, ...]
    demands: tuple[SceneDemand, ...]
    pins: tuple[Pin, ...]
    availability: tuple[AvailabilityBlock, ...]
    durations: dict[str, int]
    infeasible: tuple[Conflict, ...]
    conflicts: tuple[Conflict, ...]
    labeled_stale: bool = False
    config_node_id: str | None = None
    analysis_node_id: str | None = None

    @property
    def id(self) -> str:
        return self.projection.id

    @property
    def project_id(self) -> str:
        return self.projection.project_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection": self.projection.to_dict(),
            "breakdown_id": self.breakdown_id,
            "seed": self.seed,
            "boards": [item.to_dict() for item in self.boards],
            "demands": [item.to_dict() for item in self.demands],
            "pins": [item.to_dict() for item in self.pins],
            "availability": [item.to_dict() for item in self.availability],
            "durations": dict(self.durations),
            "infeasible": [item.to_dict() for item in self.infeasible],
            "conflicts": [item.to_dict() for item in self.conflicts],
            "labeled_stale": self.labeled_stale,
            "config_node_id": self.config_node_id,
            "analysis_node_id": self.analysis_node_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredSchedule:
        return cls(
            projection=ProductionProjection.from_dict(data["projection"]),
            breakdown_id=str(data["breakdown_id"]),
            seed=int(data["seed"]),
            boards=tuple(Board.from_dict(item) for item in data.get("boards", ())),
            demands=tuple(SceneDemand.from_dict(item) for item in data.get("demands", ())),
            pins=tuple(Pin.from_dict(item) for item in data.get("pins", ())),
            availability=tuple(
                AvailabilityBlock.from_dict(item) for item in data.get("availability", ())
            ),
            durations={str(key): int(value) for key, value in dict(data.get("durations", {})).items()},
            infeasible=tuple(Conflict.from_dict(item) for item in data.get("infeasible", ())),
            conflicts=tuple(Conflict.from_dict(item) for item in data.get("conflicts", ())),
            labeled_stale=bool(data.get("labeled_stale", False)),
            config_node_id=str(data["config_node_id"]) if data.get("config_node_id") else None,
            analysis_node_id=(
                str(data["analysis_node_id"]) if data.get("analysis_node_id") else None
            ),
        )
