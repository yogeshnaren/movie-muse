"""SceneSpace — deterministic location geometry and blocking (architecture §13).

SceneSpace owns location geometry, subject positions, and blocking; ShotIR
(``movie_muse.schemas.shot_ir``) references a SceneSpace and layers camera
and composition on top of it. Image/video models are replaceable renderers
of the shots these types define, never the source of truth for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict, tuple_of


@dataclass(frozen=True, slots=True)
class SubjectPosition:
    subject_id: str
    x: float
    y: float
    orientation_degrees: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubjectPosition:
        return dataclass_from_dict(cls, data)


@dataclass(frozen=True, slots=True)
class SceneSpace:
    SCHEMA_NAME: ClassVar[str] = "scene_space"

    id: str
    scene_id: str
    geometry_description: str
    subject_positions: tuple[SubjectPosition, ...] = ()
    locked_attributes: tuple[str, ...] = ()
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SceneSpace:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "subject_positions": tuple_of(SubjectPosition.from_dict),
                "locked_attributes": tuple,
            },
        )
