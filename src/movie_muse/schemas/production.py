"""ProductionProjection — the generic shape for operational projections.

Architecture §3.5 (level 5, "OperationalProjections"): continuity,
breakdown, schedule constraints, resources, budget evidence, and insurance-
readiness inputs. Domain-specific modules (breakdown/scheduling/budget)
extend the ``kind``-specific ``data`` payload rather than inventing a new
projection envelope; the envelope itself, its maturity, and its staleness
labeling are defined once, here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from movie_muse.schemas.serialization import dataclass_from_dict, dataclass_to_dict, sealed


class ProjectionKind(str, Enum):
    CONTINUITY = "continuity"
    BREAKDOWN = "breakdown"
    SCHEDULE = "schedule"
    RESOURCES = "resources"
    BUDGET_EVIDENCE = "budget_evidence"
    INSURANCE_READINESS = "insurance_readiness"


class BudgetMaturity(str, Enum):
    """Architecture §13's explicit budget-maturity ladder.

    Only present when ``kind == BUDGET_EVIDENCE``; other projection kinds
    leave this ``None``.
    """

    CONCEPT_FEASIBILITY_BAND = "concept_feasibility_band"
    SCRIPT_BREAKDOWN_RANGE = "script_breakdown_range"
    PRELIMINARY_PRODUCTION_ESTIMATE = "preliminary_production_estimate"
    DEPARTMENT_CONFIRMED_WORKING_BUDGET = "department_confirmed_working_budget"
    BID_BACKED_ESTIMATE = "bid_backed_estimate"
    PRODUCTION_FORECAST_TO_COMPLETE = "production_forecast_to_complete"


@sealed
@dataclass(frozen=True, slots=True)
class ProductionProjection:
    SCHEMA_NAME: ClassVar[str] = "production_projection"

    id: str
    project_id: str
    kind: ProjectionKind
    source_revision_id: str
    computed_at: str
    data: dict[str, Any] = field(default_factory=dict)
    is_stale: bool = False
    budget_maturity: BudgetMaturity | None = None
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.kind == ProjectionKind.BUDGET_EVIDENCE and self.budget_maturity is None:
            raise ValueError("budget_evidence projections must declare a budget_maturity")
        if self.kind != ProjectionKind.BUDGET_EVIDENCE and self.budget_maturity is not None:
            raise ValueError("budget_maturity is only meaningful for budget_evidence projections")

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProductionProjection:
        return dataclass_from_dict(
            cls,
            data,
            converters={
                "kind": ProjectionKind,
                "budget_maturity": lambda v: BudgetMaturity(v) if v is not None else None,
            },
        )
