"""Divergence routes, sessions, and consent-gated metrics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RouteKind(str, Enum):
    BEHAVIORAL = "behavioral"
    POWER_INVERSION = "power_inversion"
    SILENCE = "silence"
    MISDIRECTION = "misdirection"
    VISUAL = "visual"
    STRUCTURAL = "structural"
    PRODUCTION_CONSTRAINED = "production_constrained"
    RADICAL_DELETE = "radical_delete"


class MetricKind(str, Enum):
    RETAINED_SUGGESTION = "retained_suggestion"
    POST_ACCEPT_EDIT = "post_accept_edit"
    USEFULNESS = "usefulness"


@dataclass(frozen=True, slots=True)
class DivergenceRoute:
    id: str
    kind: RouteKind
    preserved: tuple[str, ...]
    changed: tuple[str, ...]
    rationale: str
    candidate_text: str
    proposal_id: str
    branch_id: str
    prose: str | None = None
    provenance_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "preserved": list(self.preserved),
            "changed": list(self.changed),
            "rationale": self.rationale,
            "candidate_text": self.candidate_text,
            "proposal_id": self.proposal_id,
            "branch_id": self.branch_id,
            "prose": self.prose,
            "provenance_id": self.provenance_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DivergenceRoute:
        prose = data.get("prose")
        provenance = data.get("provenance_id")
        return cls(
            id=str(data["id"]),
            kind=RouteKind(str(data["kind"])),
            preserved=tuple(str(item) for item in data.get("preserved", ())),
            changed=tuple(str(item) for item in data.get("changed", ())),
            rationale=str(data["rationale"]),
            candidate_text=str(data["candidate_text"]),
            proposal_id=str(data["proposal_id"]),
            branch_id=str(data["branch_id"]),
            prose=str(prose) if prose is not None else None,
            provenance_id=str(provenance) if provenance is not None else None,
        )


@dataclass(frozen=True, slots=True)
class DivergenceSession:
    id: str
    project_id: str
    base_revision_id: str
    routes: tuple[DivergenceRoute, ...]
    rejected_ideas: tuple[str, ...]
    invariants: tuple[str, ...]
    model_decision_id: str | None = None

    def route(self, route_id: str) -> DivergenceRoute:
        for item in self.routes:
            if item.id == route_id:
                return item
        raise KeyError(route_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "base_revision_id": self.base_revision_id,
            "routes": [item.to_dict() for item in self.routes],
            "rejected_ideas": list(self.rejected_ideas),
            "invariants": list(self.invariants),
            "model_decision_id": self.model_decision_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DivergenceSession:
        decision = data.get("model_decision_id")
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            base_revision_id=str(data["base_revision_id"]),
            routes=tuple(DivergenceRoute.from_dict(item) for item in data.get("routes", ())),
            rejected_ideas=tuple(str(item) for item in data.get("rejected_ideas", ())),
            invariants=tuple(str(item) for item in data.get("invariants", ())),
            model_decision_id=str(decision) if decision is not None else None,
        )


@dataclass(frozen=True, slots=True)
class MetricRecord:
    id: str
    kind: MetricKind
    session_id: str
    target_id: str
    consent_granted: bool
    training_eligible: bool
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "session_id": self.session_id,
            "target_id": self.target_id,
            "consent_granted": self.consent_granted,
            "training_eligible": self.training_eligible,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricRecord:
        return cls(
            id=str(data["id"]),
            kind=MetricKind(str(data["kind"])),
            session_id=str(data["session_id"]),
            target_id=str(data["target_id"]),
            consent_granted=bool(data["consent_granted"]),
            training_eligible=bool(data["training_eligible"]),
            payload=dict(data.get("payload") or {}),
        )
