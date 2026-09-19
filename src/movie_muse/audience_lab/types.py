"""Evidence tiers, synthetic hypotheses, human samples, and calibration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

DISCLAIMER = (
    "Synthetic LLM personas are hypotheses, not human samples, not bootstrap "
    "population samples, and not demographic population estimates."
)
NON_INDEPENDENCE_NOTICE = (
    "Repeated LLM personas from the same model and prompt family are "
    "non-independent; they are not a bootstrap of a human population."
)
FORBIDDEN_POPULATION_PHRASES: tuple[str, ...] = (
    "human sample",
    "human samples",
    "bootstrap population",
    "demographic population",
    "representative sample",
    "statistically significant",
    "population estimate",
    "human respondents",
    "survey of people",
)


class EvidenceTier(str, Enum):
    SYNTHETIC_LLM = "synthetic_llm_hypothesis"
    EXPERT_READER = "expert_reader"
    TABLE_READ_PANEL = "table_read_panel"
    PREVIS_SCREENING = "previs_screening"
    RELEASED_OUTCOME = "released_outcome"


HUMAN_TIERS = frozenset(
    {
        EvidenceTier.EXPERT_READER,
        EvidenceTier.TABLE_READ_PANEL,
        EvidenceTier.PREVIS_SCREENING,
        EvidenceTier.RELEASED_OUTCOME,
    }
)


class ConsentState(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    project_id: str
    state: ConsentState
    actor_id: str | None = None
    decided_at: str | None = None

    @property
    def granted(self) -> bool:
        return self.state is ConsentState.GRANTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "state": self.state.value,
            "actor_id": self.actor_id,
            "decided_at": self.decided_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsentRecord:
        actor_id = data.get("actor_id")
        decided_at = data.get("decided_at")
        return cls(
            project_id=str(data["project_id"]),
            state=ConsentState(str(data.get("state", ConsentState.PENDING.value))),
            actor_id=str(actor_id) if actor_id else None,
            decided_at=str(decided_at) if decided_at else None,
        )


@dataclass(frozen=True, slots=True)
class AudienceSample:
    id: str
    tier: EvidenceTier
    segment: str
    reading: str
    score: float
    uncertainty: str
    non_independent: bool
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tier": self.tier.value,
            "segment": self.segment,
            "reading": self.reading,
            "score": self.score,
            "uncertainty": self.uncertainty,
            "non_independent": self.non_independent,
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AudienceSample:
        provenance = data.get("provenance") or {}
        if not isinstance(provenance, dict):
            raise ValueError("audience sample provenance is not an object")
        return cls(
            id=str(data["id"]),
            tier=EvidenceTier(str(data["tier"])),
            segment=str(data["segment"]),
            reading=str(data["reading"]),
            score=float(data["score"]),
            uncertainty=str(data["uncertainty"]),
            non_independent=bool(data["non_independent"]),
            provenance=dict(provenance),
        )


@dataclass(frozen=True, slots=True)
class SegmentHypothesis:
    id: str
    project_id: str
    segment: str
    statement: str
    labeled_hypothesis: bool = True
    population_estimate: bool = False
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "segment": self.segment,
            "statement": self.statement,
            "labeled_hypothesis": self.labeled_hypothesis,
            "population_estimate": self.population_estimate,
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SegmentHypothesis:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            segment=str(data["segment"]),
            statement=str(data["statement"]),
            labeled_hypothesis=bool(data.get("labeled_hypothesis", True)),
            population_estimate=bool(data.get("population_estimate", False)),
            disclaimer=str(data.get("disclaimer", DISCLAIMER)),
        )


@dataclass(frozen=True, slots=True)
class LabRun:
    id: str
    project_id: str
    tier: EvidenceTier
    segment: str
    prompt: str
    input_fingerprint: str
    samples: tuple[AudienceSample, ...]
    mean_score: float
    variance: float
    uncertainty: str
    non_independent: bool
    source_revision_id: str
    parent_id: str | None = None
    rights_source_id: str | None = None
    disclaimer: str = DISCLAIMER

    @property
    def is_synthetic(self) -> bool:
        return self.tier is EvidenceTier.SYNTHETIC_LLM

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "tier": self.tier.value,
            "segment": self.segment,
            "prompt": self.prompt,
            "input_fingerprint": self.input_fingerprint,
            "samples": [item.to_dict() for item in self.samples],
            "mean_score": self.mean_score,
            "variance": self.variance,
            "uncertainty": self.uncertainty,
            "non_independent": self.non_independent,
            "source_revision_id": self.source_revision_id,
            "parent_id": self.parent_id,
            "rights_source_id": self.rights_source_id,
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LabRun:
        raw_samples = data.get("samples", ())
        if not isinstance(raw_samples, list | tuple):
            raise ValueError("lab run samples is not a list")
        parent_id = data.get("parent_id")
        rights_source_id = data.get("rights_source_id")
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            tier=EvidenceTier(str(data["tier"])),
            segment=str(data["segment"]),
            prompt=str(data["prompt"]),
            input_fingerprint=str(data["input_fingerprint"]),
            samples=tuple(AudienceSample.from_dict(dict(item)) for item in raw_samples),
            mean_score=float(data["mean_score"]),
            variance=float(data["variance"]),
            uncertainty=str(data["uncertainty"]),
            non_independent=bool(data["non_independent"]),
            source_revision_id=str(data["source_revision_id"]),
            parent_id=str(parent_id) if parent_id else None,
            rights_source_id=str(rights_source_id) if rights_source_id else None,
            disclaimer=str(data.get("disclaimer", DISCLAIMER)),
        )


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    id: str
    project_id: str
    synthetic_run_id: str
    human_run_id: str
    residual: float
    coverage: float
    population_estimate: bool = False
    disclaimer: str = (
        "This residual is a within-lab comparison, not a validated population estimate."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "synthetic_run_id": self.synthetic_run_id,
            "human_run_id": self.human_run_id,
            "residual": self.residual,
            "coverage": self.coverage,
            "population_estimate": self.population_estimate,
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationReport:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            synthetic_run_id=str(data["synthetic_run_id"]),
            human_run_id=str(data["human_run_id"]),
            residual=float(data["residual"]),
            coverage=float(data["coverage"]),
            population_estimate=bool(data.get("population_estimate", False)),
            disclaimer=str(
                data.get(
                    "disclaimer",
                    "This residual is a within-lab comparison, not a validated population estimate.",
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class IntendedEffectComparison:
    run_id: str
    intent_id: str
    intent_statement: str
    overlap: float
    advisory: bool = True
    disclaimer: str = "Intended-effect comparison is advisory and does not prove audience outcome."

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "intent_id": self.intent_id,
            "intent_statement": self.intent_statement,
            "overlap": self.overlap,
            "advisory": self.advisory,
            "disclaimer": self.disclaimer,
        }
