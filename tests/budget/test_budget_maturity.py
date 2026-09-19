"""Maturity calibration and fail-closed accuracy claims."""

from __future__ import annotations

import pytest

from movie_muse.budget.api import AccuracyClaimError, AmountEvidence
from movie_muse.schemas.api import BudgetMaturity


def test_preliminary_budget_refuses_extremely_accurate_claim(
    compiled_schedule, budget_stack
) -> None:
    stored = budget_stack.budget.compile(
        compiled_schedule.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
        maturity=BudgetMaturity.PRELIMINARY_PRODUCTION_ESTIMATE,
    )
    assert stored.calibration.validated is False
    assert "extremely accurate" in stored.calibration.disclaimer.casefold()
    dimensions = {item.dimension for item in stored.calibration.slices}
    assert dimensions == {"maturity", "department", "geography", "budget_class"}
    with pytest.raises(AccuracyClaimError):
        budget_stack.budget.claim_accuracy(
            stored.id,
            "this is extremely accurate",
            principal=budget_stack.principal,
            acl_epoch=budget_stack.epoch,
        )


def test_forecast_with_actuals_can_claim_measured_accuracy(
    compiled_schedule, budget_stack
) -> None:
    stored = budget_stack.budget.compile(
        compiled_schedule.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
        maturity=BudgetMaturity.PRODUCTION_FORECAST_TO_COMPLETE,
    )
    evidence = AmountEvidence(
        source="payroll actual",
        as_of_date="2026-09-19",
        territory="US",
        currency="USD",
    )
    with_actual = budget_stack.budget.add_actual(
        stored.id,
        stored.lines[0].id,
        stored.lines[0].amount,
        evidence,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    # recompile-equivalent calibration via add_actual does not flip validated
    # until maturity is forecast AND actuals exist on the stored calibration.
    refreshed = budget_stack.budget.compile(
        compiled_schedule.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
        maturity=BudgetMaturity.PRODUCTION_FORECAST_TO_COMPLETE,
        budget_id=with_actual.id,
    )
    assert refreshed.calibration.validated is True
    report = budget_stack.budget.claim_accuracy(
        refreshed.id,
        "this is extremely accurate",
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    assert report.validated is True
    assert any(item.dimension == "department" for item in report.slices)


def test_sensitivity_does_not_mutate_canon(compiled_schedule, budget_stack) -> None:
    stored = budget_stack.budget.compile(
        compiled_schedule.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    scenario = budget_stack.budget.sensitivity(
        stored.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
        rate_delta="0.10",
        label="P90 rates",
    )
    assert scenario.total != stored.total
    reloaded = budget_stack.budget.get_budget(
        stored.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    assert reloaded.total == stored.total
