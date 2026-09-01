"""ShotIR — deterministic camera/composition definition of one shot.

Architecture §13: camera position/height/orientation/sensor/lens/movement,
composition, eyelines, light direction, color, performance intent,
continuity, locked attributes, and annotations. Image/video models render a
defined ShotIR; they do not define it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict


@dataclass(frozen=True, slots=True)
class CameraSpec:
    position_x: float
    position_y: float
    height_m: float
    orientation_degrees: float
    sensor: str
    lens_mm: float
    movement: str = "static"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CameraSpec:
        return dataclass_from_dict(cls, data)


@dataclass(frozen=True, slots=True)
class ShotIR:
    SCHEMA_NAME: ClassVar[str] = "shot_ir"

    id: str
    scene_space_id: str
    camera: CameraSpec
    composition_notes: str
    light_direction: str
    performance_intent: str
    created_at: str
    eyeline_subject_ids: tuple[str, ...] = ()
    locked_attributes: tuple[str, ...] = ()
    annotations: tuple[str, ...] = ()
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShotIR:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "camera": CameraSpec.from_dict,
                "eyeline_subject_ids": tuple,
                "locked_attributes": tuple,
                "annotations": tuple,
            },
        )
