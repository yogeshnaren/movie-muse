"""Typed fixture, expected-artifact, and MovieMuse Bench records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import ScreenplayDocument
from movie_muse.testkit.errors import UniversalScoreForbiddenError


class FixtureClass(str, Enum):
    SMALL = "small"
    FEATURE_COMPLETE = "feature_complete"
    PRODUCTION = "production"
    ADVERSARIAL = "adversarial"


class ExpectedKind(str, Enum):
    AST = "ast"
    LAYOUT = "layout"
    FILM_IR = "film_ir"


class ExpectedStatus(str, Enum):
    CURRENT = "current"
    DEFERRED = "deferred"


class EvaluationFamily(str, Enum):
    OBJECTIVE_GROUND_TRUTH = "objective_ground_truth"
    BLINDED_HUMAN_PREFERENCE = "blinded_human_preference"
    OBSERVED_WORKFLOW_UTILITY = "observed_workflow_utility"


KNOWN_PRODUCERS = frozenset({"document_kernel"})
REQUIRED_CURRENT_KINDS = frozenset({ExpectedKind.AST})

REQUIRED_PRODUCTION_EDGES = frozenset(
    {
        "title_page",
        "scene_heading",
        "action",
        "character",
        "dialogue",
        "parenthetical",
        "dual_dialogue",
        "transition",
        "shot",
        "lyrics",
        "general_text",
        "notes",
        "tags",
        "revisions",
        "locked_pages",
        "locked_scenes",
        "omitted_scenes",
        "ab_scenes",
        "unicode",
        "rtl",
        "unknown_extensions",
    }
)

DEFERRED_AWAITING = {
    ExpectedKind.LAYOUT: "MM-014",
    ExpectedKind.FILM_IR: "MM-018",
}

SYNTHETIC_AUDIENCE_DISCLAIMER = "Synthetic audiences are hypotheses, not human samples."


@dataclass(frozen=True, slots=True)
class FixtureRights:
    classification: str
    license: str
    consent: str
    origin: str
    allow_training: bool
    permitted_uses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FixtureManifest:
    id: str
    fixture_class: FixtureClass
    title: str
    edges: tuple[str, ...]
    license_file: str
    rights_file: str


@dataclass(frozen=True, slots=True)
class ScreenplayFixture:
    manifest: FixtureManifest
    document: ScreenplayDocument
    rights: FixtureRights
    license_text: str
    directory: str


@dataclass(frozen=True, slots=True)
class ExpectedArtifact:
    """Declared expected output. Deferred records are not silently compared."""

    kind: ExpectedKind
    status: ExpectedStatus
    producer: str | None
    awaiting: str | None
    schema_version: str = "1.0"
    payload: dict[str, Any] | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "status": self.status.value,
            "producer": self.producer,
            "awaiting": self.awaiting,
            "schema_version": self.schema_version,
            "payload": self.payload,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExpectedArtifact:
        payload = data.get("payload")
        return cls(
            kind=ExpectedKind(str(data["kind"])),
            status=ExpectedStatus(str(data["status"])),
            producer=str(data["producer"]) if data.get("producer") is not None else None,
            awaiting=str(data["awaiting"]) if data.get("awaiting") is not None else None,
            schema_version=str(data.get("schema_version") or "1.0"),
            payload=dict(payload) if isinstance(payload, dict) else None,
            note=str(data["note"]) if data.get("note") is not None else None,
        )


@dataclass(frozen=True, slots=True)
class GoldenApproval:
    fixture_id: str
    kind: ExpectedKind
    payload_digest: str
    token: str
    signature: str


@dataclass(frozen=True, slots=True)
class DecodingSettings:
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 0

    def to_dict(self) -> dict[str, float | int]:
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "seed": self.seed,
        }


@dataclass(frozen=True, slots=True)
class TaskConfiguration:
    """Complete evaluation configuration. Identity is not model brand alone."""

    model: str
    prompt: str
    context_strategy: str
    tools: tuple[str, ...]
    decoding: DecodingSettings
    schema: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "prompt": self.prompt,
            "context_strategy": self.context_strategy,
            "tools": list(self.tools),
            "decoding": self.decoding.to_dict(),
            "schema": self.schema,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskConfiguration:
        decoding_raw = data.get("decoding") or {}
        decoding = DecodingSettings(
            temperature=float(decoding_raw.get("temperature", 0.0)),
            top_p=float(decoding_raw.get("top_p", 1.0)),
            seed=int(decoding_raw.get("seed", 0)),
        )
        tools = tuple(str(item) for item in (data.get("tools") or ()))
        return cls(
            model=str(data["model"]),
            prompt=str(data["prompt"]),
            context_strategy=str(data["context_strategy"]),
            tools=tools,
            decoding=decoding,
            schema=str(data["schema"]),
        )


@dataclass(frozen=True, slots=True)
class BlindedPreferenceLabel:
    rater_id: str
    winner_configuration_id: str
    loser_configuration_id: str
    blinded: bool
    notes: str = ""


@dataclass(frozen=True, slots=True)
class BenchTask:
    id: str
    family: EvaluationFamily
    configuration: TaskConfiguration
    fixture_id: str | None = None
    labels: tuple[BlindedPreferenceLabel, ...] = ()
    utility_metric: str | None = None
    disclaimer: str | None = None


@dataclass(frozen=True, slots=True)
class FamilyScore:
    family: EvaluationFamily
    value: float
    method: str
    configuration_id: str
    assumptions: tuple[str, ...] = ()
    uncertainty: str = "fixture"


@dataclass(frozen=True, slots=True)
class BenchReport:
    configuration_id: str
    scores: tuple[FamilyScore, ...]

    def score_for(self, family: EvaluationFamily) -> FamilyScore:
        for score in self.scores:
            if score.family is family:
                return score
        raise KeyError(family.value)

    def collapse_to_universal_score(self) -> float:
        raise UniversalScoreForbiddenError(
            "MovieMuse Bench cannot collapse evaluation families into one MovieMuseScore"
        )
