"""Configurable rubric criteria, evidence-linked ratings, and advisory analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

DISCLAIMER = (
    "Rubric analysis is advisory. Scores are not canon, not a FilmIR write, "
    "and not a CreativeIntentIR write."
)
REQUIRED_CRITERIA: tuple[str, ...] = (
    "clarity",
    "character",
    "pacing",
    "theme",
    "emotion",
    "producibility",
    "intended_effect",
)


class CriterionKind(str, Enum):
    CLARITY = "clarity"
    CHARACTER = "character"
    PACING = "pacing"
    THEME = "theme"
    EMOTION = "emotion"
    PRODUCIBILITY = "producibility"
    INTENDED_EFFECT = "intended_effect"


class RaterKind(str, Enum):
    HUMAN = "human"
    MODEL = "model"


def default_criteria() -> tuple[CriterionSpec, ...]:
    descriptions = {
        CriterionKind.CLARITY: "Story events and causal links are readable.",
        CriterionKind.CHARACTER: "Character want, obstacle, and change are evidenced.",
        CriterionKind.PACING: "Scene duration and beat density serve the intended rhythm.",
        CriterionKind.THEME: "Thematic statement is supported by structural facts.",
        CriterionKind.EMOTION: "Emotional turns are linked to scene evidence.",
        CriterionKind.PRODUCIBILITY: "Craft load is visible from structural facts.",
        CriterionKind.INTENDED_EFFECT: "Stated audience experience is compared, not proven.",
    }
    return tuple(
        CriterionSpec(kind=kind, description=descriptions[kind], weight=1.0)
        for kind in CriterionKind
    )


@dataclass(frozen=True, slots=True)
class CriterionSpec:
    kind: CriterionKind
    description: str
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "description": self.description,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CriterionSpec:
        return cls(
            kind=CriterionKind(str(data["kind"])),
            description=str(data["description"]),
            weight=float(data.get("weight", 1.0)),
        )


@dataclass(frozen=True, slots=True)
class RubricDefinition:
    id: str
    project_id: str
    name: str
    version: str
    criteria: tuple[CriterionSpec, ...]
    advisory: bool = True
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "version": self.version,
            "criteria": [item.to_dict() for item in self.criteria],
            "advisory": self.advisory,
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RubricDefinition:
        raw_criteria = data.get("criteria", ())
        if not isinstance(raw_criteria, list | tuple):
            raise ValueError("rubric criteria is not a list")
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            name=str(data["name"]),
            version=str(data["version"]),
            criteria=tuple(CriterionSpec.from_dict(dict(item)) for item in raw_criteria),
            advisory=bool(data.get("advisory", True)),
            disclaimer=str(data.get("disclaimer", DISCLAIMER)),
        )


@dataclass(frozen=True, slots=True)
class Rating:
    id: str
    analysis_id: str
    criterion: CriterionKind
    score: float
    evidence_refs: tuple[str, ...]
    rationale: str
    rater_kind: RaterKind
    rater_id: str
    rubric_id: str
    rubric_version: str
    confidence: float
    input_fingerprint: str
    model_id: str | None = None
    parent_rating_id: str | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "criterion": self.criterion.value,
            "score": self.score,
            "evidence_refs": list(self.evidence_refs),
            "rationale": self.rationale,
            "rater_kind": self.rater_kind.value,
            "rater_id": self.rater_id,
            "rubric_id": self.rubric_id,
            "rubric_version": self.rubric_version,
            "confidence": self.confidence,
            "input_fingerprint": self.input_fingerprint,
            "model_id": self.model_id,
            "parent_rating_id": self.parent_rating_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rating:
        refs = data.get("evidence_refs", ())
        if not isinstance(refs, list | tuple):
            raise ValueError("rating evidence_refs is not a list")
        model_id = data.get("model_id")
        parent_rating_id = data.get("parent_rating_id")
        return cls(
            id=str(data["id"]),
            analysis_id=str(data["analysis_id"]),
            criterion=CriterionKind(str(data["criterion"])),
            score=float(data["score"]),
            evidence_refs=tuple(str(item) for item in refs),
            rationale=str(data["rationale"]),
            rater_kind=RaterKind(str(data["rater_kind"])),
            rater_id=str(data["rater_id"]),
            rubric_id=str(data["rubric_id"]),
            rubric_version=str(data["rubric_version"]),
            confidence=float(data["confidence"]),
            input_fingerprint=str(data["input_fingerprint"]),
            model_id=str(model_id) if model_id else None,
            parent_rating_id=str(parent_rating_id) if parent_rating_id else None,
            created_at=str(data.get("created_at", "")),
        )


@dataclass(frozen=True, slots=True)
class CounterEvidence:
    id: str
    analysis_id: str
    statement: str
    evidence_refs: tuple[str, ...]
    actor_id: str
    rating_id: str | None = None
    criterion: CriterionKind | None = None
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "statement": self.statement,
            "evidence_refs": list(self.evidence_refs),
            "actor_id": self.actor_id,
            "rating_id": self.rating_id,
            "criterion": self.criterion.value if self.criterion is not None else None,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CounterEvidence:
        refs = data.get("evidence_refs", ())
        if not isinstance(refs, list | tuple):
            raise ValueError("counter-evidence evidence_refs is not a list")
        rating_id = data.get("rating_id")
        raw_criterion = data.get("criterion")
        return cls(
            id=str(data["id"]),
            analysis_id=str(data["analysis_id"]),
            statement=str(data["statement"]),
            evidence_refs=tuple(str(item) for item in refs),
            actor_id=str(data["actor_id"]),
            rating_id=str(rating_id) if rating_id else None,
            criterion=CriterionKind(str(raw_criterion)) if raw_criterion else None,
            created_at=str(data.get("created_at", "")),
        )


@dataclass(frozen=True, slots=True)
class CreatorOverride:
    id: str
    analysis_id: str
    criterion: CriterionKind
    score: float
    evidence_refs: tuple[str, ...]
    rationale: str
    actor_id: str
    prior_rating_ids: tuple[str, ...]
    created_at: str = ""
    deletes_prior: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "criterion": self.criterion.value,
            "score": self.score,
            "evidence_refs": list(self.evidence_refs),
            "rationale": self.rationale,
            "actor_id": self.actor_id,
            "prior_rating_ids": list(self.prior_rating_ids),
            "created_at": self.created_at,
            "deletes_prior": self.deletes_prior,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreatorOverride:
        refs = data.get("evidence_refs", ())
        priors = data.get("prior_rating_ids", ())
        if not isinstance(refs, list | tuple) or not isinstance(priors, list | tuple):
            raise ValueError("override lists are invalid")
        return cls(
            id=str(data["id"]),
            analysis_id=str(data["analysis_id"]),
            criterion=CriterionKind(str(data["criterion"])),
            score=float(data["score"]),
            evidence_refs=tuple(str(item) for item in refs),
            rationale=str(data["rationale"]),
            actor_id=str(data["actor_id"]),
            prior_rating_ids=tuple(str(item) for item in priors),
            created_at=str(data.get("created_at", "")),
            deletes_prior=bool(data.get("deletes_prior", False)),
        )


@dataclass(frozen=True, slots=True)
class RubricAnalysis:
    id: str
    project_id: str
    rubric_id: str
    rubric_version: str
    film_ir_id: str
    source_revision_id: str
    intent_ids: tuple[str, ...]
    input_fingerprint: str
    rating_ids: tuple[str, ...] = ()
    override_ids: tuple[str, ...] = ()
    counter_evidence_ids: tuple[str, ...] = ()
    parent_id: str | None = None
    probe_delta: str | None = None
    advisory: bool = True
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "rubric_id": self.rubric_id,
            "rubric_version": self.rubric_version,
            "film_ir_id": self.film_ir_id,
            "source_revision_id": self.source_revision_id,
            "intent_ids": list(self.intent_ids),
            "input_fingerprint": self.input_fingerprint,
            "rating_ids": list(self.rating_ids),
            "override_ids": list(self.override_ids),
            "counter_evidence_ids": list(self.counter_evidence_ids),
            "parent_id": self.parent_id,
            "probe_delta": self.probe_delta,
            "advisory": self.advisory,
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RubricAnalysis:
        def _ids(key: str) -> tuple[str, ...]:
            raw = data.get(key, ())
            if not isinstance(raw, list | tuple):
                raise ValueError(f"analysis {key} is not a list")
            return tuple(str(item) for item in raw)

        parent_id = data.get("parent_id")
        probe_delta = data.get("probe_delta")
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            rubric_id=str(data["rubric_id"]),
            rubric_version=str(data["rubric_version"]),
            film_ir_id=str(data["film_ir_id"]),
            source_revision_id=str(data["source_revision_id"]),
            intent_ids=_ids("intent_ids"),
            input_fingerprint=str(data["input_fingerprint"]),
            rating_ids=_ids("rating_ids"),
            override_ids=_ids("override_ids"),
            counter_evidence_ids=_ids("counter_evidence_ids"),
            parent_id=str(parent_id) if parent_id else None,
            probe_delta=str(probe_delta) if probe_delta else None,
            advisory=bool(data.get("advisory", True)),
            disclaimer=str(data.get("disclaimer", DISCLAIMER)),
        )


@dataclass(frozen=True, slots=True)
class DisagreementReport:
    analysis_id: str
    criterion: CriterionKind
    scores: tuple[float, ...]
    spread: float
    confidence: float
    rater_count: int
    advisory: bool = True
    disclaimer: str = "Disagreement is advisory and does not replace creator judgment."

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "criterion": self.criterion.value,
            "scores": list(self.scores),
            "spread": self.spread,
            "confidence": self.confidence,
            "rater_count": self.rater_count,
            "advisory": self.advisory,
            "disclaimer": self.disclaimer,
        }


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    left_analysis_id: str
    right_analysis_id: str
    residual: float
    coverage: float
    advisory: bool = True
    population_estimate: bool = False
    disclaimer: str = (
        "This residual is an advisory within-lab comparison, not a canon score "
        "and not a population estimate."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "left_analysis_id": self.left_analysis_id,
            "right_analysis_id": self.right_analysis_id,
            "residual": self.residual,
            "coverage": self.coverage,
            "advisory": self.advisory,
            "population_estimate": self.population_estimate,
            "disclaimer": self.disclaimer,
        }


@dataclass(frozen=True, slots=True)
class ScoreTrace:
    rating_id: str
    analysis_id: str
    criterion: CriterionKind
    score: float
    film_ir_id: str
    source_revision_id: str
    evidence_refs: tuple[str, ...]
    model_id: str | None
    rubric_id: str
    rubric_version: str
    input_fingerprint: str
    rater_kind: RaterKind

    def to_dict(self) -> dict[str, Any]:
        return {
            "rating_id": self.rating_id,
            "analysis_id": self.analysis_id,
            "criterion": self.criterion.value,
            "score": self.score,
            "film_ir_id": self.film_ir_id,
            "source_revision_id": self.source_revision_id,
            "evidence_refs": list(self.evidence_refs),
            "model_id": self.model_id,
            "rubric_id": self.rubric_id,
            "rubric_version": self.rubric_version,
            "input_fingerprint": self.input_fingerprint,
            "rater_kind": self.rater_kind.value,
        }
