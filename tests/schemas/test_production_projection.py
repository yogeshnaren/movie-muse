"""ProductionProjection envelope: operational data is frozen after construction."""

from __future__ import annotations

import pytest

from movie_muse.schemas import ids, validators
from movie_muse.schemas.production import BudgetMaturity, ProductionProjection, ProjectionKind


def test_valid_breakdown_projection_validates() -> None:
    projection = ProductionProjection(
        id=ids.new_id("production_projection"),
        project_id=ids.new_id("project"),
        kind=ProjectionKind.BREAKDOWN,
        source_revision_id=ids.new_id("revision"),
        computed_at="2026-09-01T00:00:00Z",
        data={"department": "props", "items": [{"name": "lockpick set"}]},
    )
    validators.validate_payload("production_projection", projection.to_dict())


def test_budget_evidence_requires_maturity() -> None:
    with pytest.raises(ValueError, match="budget_maturity"):
        ProductionProjection(
            id=ids.new_id("production_projection"),
            project_id=ids.new_id("project"),
            kind=ProjectionKind.BUDGET_EVIDENCE,
            source_revision_id=ids.new_id("revision"),
            computed_at="2026-09-01T00:00:00Z",
        )


def test_non_budget_projection_rejects_maturity() -> None:
    with pytest.raises(ValueError, match="budget_maturity"):
        ProductionProjection(
            id=ids.new_id("production_projection"),
            project_id=ids.new_id("project"),
            kind=ProjectionKind.SCHEDULE,
            source_revision_id=ids.new_id("revision"),
            computed_at="2026-09-01T00:00:00Z",
            budget_maturity=BudgetMaturity.CONCEPT_FEASIBILITY_BAND,
        )


def test_projection_data_is_recursively_immutable() -> None:
    projection = ProductionProjection(
        id=ids.new_id("production_projection"),
        project_id=ids.new_id("project"),
        kind=ProjectionKind.BREAKDOWN,
        source_revision_id=ids.new_id("revision"),
        computed_at="2026-09-01T00:00:00Z",
        data={"department": "props", "items": [{"name": "lockpick set"}]},
    )
    with pytest.raises(TypeError):
        projection.data["department"] = "camera"  # type: ignore[index]
    with pytest.raises(TypeError):
        projection.data["items"][0]["name"] = "camera"  # type: ignore[index]
