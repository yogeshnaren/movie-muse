"""Epistemic-level state kinds that MUST NOT be silently interchanged.

Architecture §3.5 requires that authored facts, structural facts, inferred
semantic claims, operational assumptions, and scenario outputs have distinct
types. This module gives each level its own frozen dataclass. None of the
five classes shares a base class with the others, so:

- statically, mypy treats them as nominally unrelated types: a function typed
  to accept ``AuthoredFact`` rejects a ``StructuralFact`` argument even though
  both classes have identical field shapes (see
  ``tests/schemas/typecheck_fixtures``);
- at runtime, each level's JSON Schema pins ``kind`` to a ``const`` value and
  requires level-specific provenance fields, so validating one level's
  payload against another level's schema fails (see
  ``tests/schemas/test_epistemic_validation.py``).

There is deliberately no ``promote()`` helper that quietly upgrades one level
into another; callers must construct the target level explicitly with its own
required provenance, which is the enforcement point for "cannot be promoted
implicitly".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_to_dict, sealed


def _require_declared_kind(instance: Any) -> None:
    declared = type(instance).KIND
    actual = instance.kind
    if actual != declared:
        raise ValueError(
            f"{type(instance).__name__} kind must be {declared.value!r}, not {getattr(actual, 'value', actual)!r}"
        )


class EpistemicLevel(str, Enum):
    AUTHORED = "authored"
    STRUCTURAL = "structural"
    INFERRED = "inferred"
    OPERATIONAL = "operational"
    SCENARIO = "scenario"


@sealed
@dataclass(frozen=True, slots=True)
class AuthoredFact:
    """A creator-authored, canon-backed fact (e.g. a line in the screenplay)."""

    KIND: ClassVar[EpistemicLevel] = EpistemicLevel.AUTHORED
    SCHEMA_NAME: ClassVar[str] = "authored_fact"

    id: str
    subject_id: str
    attribute: str
    value: Any
    source_revision_id: str
    author_actor_id: str
    kind: EpistemicLevel = EpistemicLevel.AUTHORED
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        _require_declared_kind(self)

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@sealed
@dataclass(frozen=True, slots=True)
class StructuralFact:
    """A deterministically derived fact (e.g. FilmIR scene/entity extraction)."""

    KIND: ClassVar[EpistemicLevel] = EpistemicLevel.STRUCTURAL
    SCHEMA_NAME: ClassVar[str] = "structural_fact"

    id: str
    subject_id: str
    attribute: str
    value: Any
    derived_from_revision_id: str
    extractor_version: str
    kind: EpistemicLevel = EpistemicLevel.STRUCTURAL
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        _require_declared_kind(self)

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@sealed
@dataclass(frozen=True, slots=True)
class InferredClaim:
    """A probabilistic semantic claim with confidence and provenance."""

    KIND: ClassVar[EpistemicLevel] = EpistemicLevel.INFERRED
    SCHEMA_NAME: ClassVar[str] = "inferred_claim"

    id: str
    subject_id: str
    attribute: str
    value: Any
    confidence: float
    evidence_bundle_id: str
    model_id: str
    kind: EpistemicLevel = EpistemicLevel.INFERRED
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        _require_declared_kind(self)
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be within [0.0, 1.0]")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@sealed
@dataclass(frozen=True, slots=True)
class OperationalAssumption:
    """An operational-projection assumption (breakdown/schedule/budget input)."""

    KIND: ClassVar[EpistemicLevel] = EpistemicLevel.OPERATIONAL
    SCHEMA_NAME: ClassVar[str] = "operational_assumption"

    id: str
    subject_id: str
    attribute: str
    value: Any
    assumed_by_actor_id: str
    valid_until_revision_id: str | None = None
    kind: EpistemicLevel = EpistemicLevel.OPERATIONAL
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        _require_declared_kind(self)

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@sealed
@dataclass(frozen=True, slots=True)
class ScenarioOutput:
    """A commercial/audience scenario output; never a guarantee or forecast fact."""

    KIND: ClassVar[EpistemicLevel] = EpistemicLevel.SCENARIO
    SCHEMA_NAME: ClassVar[str] = "scenario_output"

    id: str
    subject_id: str
    attribute: str
    value: Any
    scenario_model_id: str
    percentile: str | None = None
    kind: EpistemicLevel = EpistemicLevel.SCENARIO
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        _require_declared_kind(self)

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


EPISTEMIC_TYPES_BY_LEVEL: dict[EpistemicLevel, type[Any]] = {
    EpistemicLevel.AUTHORED: AuthoredFact,
    EpistemicLevel.STRUCTURAL: StructuralFact,
    EpistemicLevel.INFERRED: InferredClaim,
    EpistemicLevel.OPERATIONAL: OperationalAssumption,
    EpistemicLevel.SCENARIO: ScenarioOutput,
}
