"""P10/P50/P90 scenarios require traces; OOD and thin coverage fail closed."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.commercial_forecast.api import (
    DISCLAIMER,
    INSUFFICIENT_EVIDENCE,
    AssumptionError,
    AssumptionKey,
    ForecastNotFoundError,
    GuaranteeClaimError,
    InsufficientEvidenceError,
    LeakageError,
    UntracedNumberError,
)
from movie_muse.identity.api import Role


def test_forecast_emits_p10_p50_p90_with_traces(forecast_stack, ready_forecast) -> None:
    stored = forecast_stack.forecast.forecast(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        budget_id=ready_forecast.id,
        as_of="2024-12-31",
    )
    assert stored.id.startswith("scm_")
    assert stored.guarantee is False
    assert stored.scenario.is_out_of_distribution is False
    percentiles = [item.percentile for item in stored.scenario.outcomes]
    assert percentiles == ["P10", "P50", "P90"]
    p10, p50, p90 = (stored.outcome(name).value for name in percentiles)
    assert p10 <= p50 <= p90
    assert len(stored.traces) == 3
    for trace in stored.traces:
        assert trace.method
        assert trace.data_as_of == "2024-12-31"
        assert trace.assumption_ids
        assert trace.comparable_ids
        assert trace.budget_id == ready_forecast.id
    summary = forecast_stack.forecast.export_summary(
        stored.id, principal=forecast_stack.principal, acl_epoch=forecast_stack.epoch
    )
    assert DISCLAIMER in summary
    assert "not a single guaranteed number" in summary


def test_repeat_forecast_reuses_fingerprint(forecast_stack, ready_forecast) -> None:
    first = forecast_stack.forecast.forecast(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        budget_id=ready_forecast.id,
        as_of="2024-12-31",
    )
    second = forecast_stack.forecast.forecast(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        budget_id=ready_forecast.id,
        as_of="2024-12-31",
    )
    assert first.id == second.id
    assert first.input_fingerprint == second.input_fingerprint


def test_missing_assumptions_fail_closed(forecast_stack, compiled_budget) -> None:
    with pytest.raises(AssumptionError, match="missing required assumptions"):
        forecast_stack.forecast.forecast(
            forecast_stack.project.id,
            principal=forecast_stack.principal,
            acl_epoch=forecast_stack.epoch,
            budget_id=compiled_budget.id,
            as_of="2024-12-31",
        )


def test_poor_coverage_is_insufficient_evidence(forecast_stack, compiled_budget) -> None:
    forecast_stack.forecast.set_assumption(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        key=AssumptionKey.DISTRIBUTION,
        value="limited theatrical plus SVOD window",
        data_as_of="2024-12-31",
        evidence="producer memo distribution",
    )
    forecast_stack.forecast.set_assumption(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        key=AssumptionKey.MARKETING,
        value="festival-to-specialty spend",
        data_as_of="2024-12-31",
        evidence="producer memo marketing",
    )
    forecast_stack.forecast.set_assumption(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        key=AssumptionKey.RELEASE,
        value="platform exclusive after 45-day theatrical",
        data_as_of="2024-12-31",
        evidence="producer memo release",
    )
    forecast_stack.forecast.set_assumption(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        key=AssumptionKey.TERRITORY,
        value="US",
        data_as_of="2024-12-31",
        evidence="producer memo territory",
    )
    forecast_stack.forecast.set_assumption(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        key=AssumptionKey.TALENT,
        value="ensemble without a global star quote",
        data_as_of="2024-12-31",
        evidence="producer memo talent",
    )
    forecast_stack.forecast.set_assumption(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        key=AssumptionKey.PLATFORM,
        value="specialty-svod",
        data_as_of="2024-12-31",
        evidence="producer memo platform",
    )
    forecast_stack.forecast.register_comparable(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        title="Only One",
        territory="US",
        platform="specialty-svod",
        budget=900_000,
        observed_gross=1_500_000,
        release_date="2023-01-01",
        data_as_of="2023-06-01",
        source="internal released-outcome ledger",
        rationale="Only One matches specialty US SVOD because of budget class.",
    )
    with pytest.raises(InsufficientEvidenceError, match=INSUFFICIENT_EVIDENCE):
        forecast_stack.forecast.forecast(
            forecast_stack.project.id,
            principal=forecast_stack.principal,
            acl_epoch=forecast_stack.epoch,
            budget_id=compiled_budget.id,
            as_of="2024-12-31",
        )


def test_ood_territory_is_insufficient_evidence(forecast_stack, ready_forecast) -> None:
    forecast_stack.forecast.set_assumption(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        key=AssumptionKey.TERRITORY,
        value="JP",
        data_as_of="2024-12-31",
        evidence="territory memo Japan",
    )
    with pytest.raises(InsufficientEvidenceError, match=INSUFFICIENT_EVIDENCE):
        forecast_stack.forecast.forecast(
            forecast_stack.project.id,
            principal=forecast_stack.principal,
            acl_epoch=forecast_stack.epoch,
            budget_id=ready_forecast.id,
            as_of="2024-12-31",
        )


def test_comparable_without_rationale_fails_closed(forecast_stack) -> None:
    with pytest.raises(UntracedNumberError, match="rationale"):
        forecast_stack.forecast.register_comparable(
            forecast_stack.project.id,
            principal=forecast_stack.principal,
            acl_epoch=forecast_stack.epoch,
            title="Bare",
            territory="US",
            platform="specialty-svod",
            budget=100.0,
            observed_gross=200.0,
            release_date="2022-01-01",
            data_as_of="2022-06-01",
            source="ledger",
            rationale="   ",
        )


def test_guarantee_language_fails_closed(forecast_stack) -> None:
    with pytest.raises(GuaranteeClaimError, match="guaranteed return"):
        forecast_stack.forecast.register_comparable(
            forecast_stack.project.id,
            principal=forecast_stack.principal,
            acl_epoch=forecast_stack.epoch,
            title="Sure Thing",
            territory="US",
            platform="specialty-svod",
            budget=100.0,
            observed_gross=200.0,
            release_date="2022-01-01",
            data_as_of="2022-06-01",
            source="ledger",
            rationale="This title is a guaranteed return.",
        )


def test_comparable_data_before_release_is_leakage(forecast_stack) -> None:
    with pytest.raises(LeakageError, match="data_as_of"):
        forecast_stack.forecast.register_comparable(
            forecast_stack.project.id,
            principal=forecast_stack.principal,
            acl_epoch=forecast_stack.epoch,
            title="Early Book",
            territory="US",
            platform="specialty-svod",
            budget=100.0,
            observed_gross=200.0,
            release_date="2024-06-01",
            data_as_of="2023-01-01",
            source="ledger",
            rationale="Specialty match on budget class.",
        )


def test_viewer_cannot_forecast(forecast_stack, ready_forecast, member) -> None:
    viewer = member(Role.VIEWER)
    with pytest.raises(AuthorizationError):
        forecast_stack.forecast.forecast(
            forecast_stack.project.id,
            principal=viewer,
            acl_epoch=forecast_stack.identity.acl_epoch(),
            budget_id=ready_forecast.id,
            as_of="2024-12-31",
        )


def test_missing_forecast_fails_closed(forecast_stack) -> None:
    with pytest.raises(ForecastNotFoundError):
        forecast_stack.forecast.get_forecast(
            "scm_missing",
            principal=forecast_stack.principal,
            acl_epoch=forecast_stack.epoch,
        )
