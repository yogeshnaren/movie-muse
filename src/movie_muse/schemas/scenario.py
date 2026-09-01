"""ScenarioModel — audience/commercial hypotheses; never a guarantee.

Architecture §3.5 (level 6, "ScenarioModels") and §13: scenarios carry
P10/P50/P90 outcomes, comparables methodology, assumptions, data dates,
model version, uncertainty/OOD warnings, and sensitivity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from movie_muse.schemas.serialization import (
    dataclass_from_dict,
    dataclass_to_dict,
    sealed,
    tuple_of,
)


@sealed
@dataclass(frozen=True, slots=True)
class ScenarioOutcome:
    percentile: str
    value: float
    unit: str

    def __post_init__(self) -> None:
        if self.percentile not in ("P10", "P50", "P90"):
            raise ValueError("percentile must be one of P10, P50, P90")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioOutcome:
        return dataclass_from_dict(cls, data)


@sealed
@dataclass(frozen=True, slots=True)
class ScenarioModel:
    SCHEMA_NAME: ClassVar[str] = "scenario_model"

    id: str
    project_id: str
    methodology_summary: str
    model_version: str
    data_as_of: str
    computed_at: str
    outcomes: tuple[ScenarioOutcome, ...]
    assumptions: tuple[str, ...] = ()
    comparables: tuple[str, ...] = ()
    uncertainty_notes: str | None = None
    is_out_of_distribution: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        percentiles = [outcome.percentile for outcome in self.outcomes]
        if len(percentiles) != len(set(percentiles)):
            raise ValueError("scenario outcomes must not repeat a percentile")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioModel:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "outcomes": tuple_of(ScenarioOutcome.from_dict),
                "assumptions": tuple,
                "comparables": tuple,
            },
        )
