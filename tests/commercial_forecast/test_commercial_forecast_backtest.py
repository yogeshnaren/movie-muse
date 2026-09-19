"""Time-split backtests, leakage fail-closed, baselines, sensitivity, audience labels."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.commercial_forecast.api import (
    INSUFFICIENT_EVIDENCE,
    AssumptionKey,
    InsufficientEvidenceError,
    LeakageError,
)
from movie_muse.identity.api import Role


def test_backtest_is_time_split_against_baseline(forecast_stack, ready_forecast) -> None:
    forecast_stack.forecast.register_comparable(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        title="Later Window",
        territory="US",
        platform="specialty-svod",
        budget=1_000_000,
        observed_gross=2_800_000,
        release_date="2025-02-01",
        data_as_of="2025-06-01",
        source="internal released-outcome ledger",
        rationale="Later Window matches specialty US SVOD because of budget class.",
    )
    report = forecast_stack.forecast.backtest(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        cutoff="2024-12-31",
    )
    assert report.id.startswith("bkt_")
    assert report.leakage is False
    assert len(report.train_ids) >= 3
    assert len(report.test_ids) >= 1
    assert "time-split" in report.method
    assert "baseline" in report.method
    assert report.model_mae >= 0.0
    assert report.baseline_mae >= 0.0
    assert ready_forecast.id


def test_backtest_rejects_future_data_in_train(forecast_stack, ready_forecast) -> None:
    forecast_stack.forecast.register_comparable(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        title="Leaked Book",
        territory="US",
        platform="specialty-svod",
        budget=900_000,
        observed_gross=2_000_000,
        release_date="2023-01-01",
        data_as_of="2025-06-01",
        source="internal released-outcome ledger",
        rationale="Leaked Book matches specialty US SVOD because of budget class.",
    )
    with pytest.raises(LeakageError, match="after the cutoff"):
        forecast_stack.forecast.backtest(
            forecast_stack.project.id,
            principal=forecast_stack.principal,
            acl_epoch=forecast_stack.epoch,
            cutoff="2024-12-31",
        )
    assert ready_forecast.id


def test_forecast_as_of_excludes_future_comparables(
    forecast_stack, ready_forecast
) -> None:
    forecast_stack.forecast.register_comparable(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        title="Unreleased Sequel",
        territory="US",
        platform="specialty-svod",
        budget=2_000_000,
        observed_gross=9_000_000,
        release_date="2026-01-01",
        data_as_of="2026-06-01",
        source="internal released-outcome ledger",
        rationale="Unreleased Sequel is a later specialty title, not used before release.",
    )
    stored = forecast_stack.forecast.forecast(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        budget_id=ready_forecast.id,
        as_of="2024-12-31",
    )
    assert all(item_id.startswith("cmp_") for item_id in stored.comparable_ids)
    listed = forecast_stack.forecast.list_forecasts(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
    )
    assert stored.id in {item.id for item in listed}


def test_thin_backtest_coverage_is_insufficient(forecast_stack) -> None:
    forecast_stack.forecast.register_comparable(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        title="Solo Train",
        territory="US",
        platform="specialty-svod",
        budget=800_000,
        observed_gross=1_000_000,
        release_date="2022-01-01",
        data_as_of="2022-06-01",
        source="internal released-outcome ledger",
        rationale="Solo Train is a specialty US SVOD peer on budget class.",
    )
    forecast_stack.forecast.register_comparable(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        title="Holdout Only",
        territory="US",
        platform="specialty-svod",
        budget=800_000,
        observed_gross=1_200_000,
        release_date="2025-01-01",
        data_as_of="2025-06-01",
        source="internal released-outcome ledger",
        rationale="Holdout Only is a later specialty US SVOD peer.",
    )
    with pytest.raises(InsufficientEvidenceError, match=INSUFFICIENT_EVIDENCE):
        forecast_stack.forecast.backtest(
            forecast_stack.project.id,
            principal=forecast_stack.principal,
            acl_epoch=forecast_stack.epoch,
            cutoff="2024-12-31",
        )


def test_sensitivity_shocks_marketing_and_stays_traced(
    forecast_stack, ready_forecast
) -> None:
    stored = forecast_stack.forecast.forecast(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        budget_id=ready_forecast.id,
        as_of="2024-12-31",
    )
    report = forecast_stack.forecast.sensitivity(
        stored.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        assumption_key=AssumptionKey.MARKETING,
        delta=0.2,
    )
    assert report.id.startswith("sns_")
    assert report.base_p50 == stored.outcome("P50").value
    assert report.shocked_p50 == pytest.approx(report.base_p50 * 1.2)
    assert report.data_as_of == stored.scenario.data_as_of
    assert "not a guaranteed" in report.method


def test_synthetic_audience_modifier_is_labeled_hypothesis(
    forecast_stack, ready_forecast
) -> None:
    run = forecast_stack.lab.run_synthetic(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        segment="specialty-us",
        prompt="How does the kitchen lock beat land for a first-time viewer?",
        sample_count=2,
    )
    stored = forecast_stack.forecast.forecast(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        budget_id=ready_forecast.id,
        as_of="2024-12-31",
        audience_run_id=run.id,
    )
    assert stored.audience_run_id == run.id
    assert "hypothesis" in stored.scenario.methodology_summary
    assert "not a population" in stored.scenario.methodology_summary
    baseline = forecast_stack.forecast.forecast(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        budget_id=ready_forecast.id,
        as_of="2024-12-31",
    )
    assert stored.id != baseline.id


def test_writer_cannot_export(forecast_stack, ready_forecast, member) -> None:
    stored = forecast_stack.forecast.forecast(
        forecast_stack.project.id,
        principal=forecast_stack.principal,
        acl_epoch=forecast_stack.epoch,
        budget_id=ready_forecast.id,
        as_of="2024-12-31",
    )
    writer = member(Role.WRITER)
    with pytest.raises(AuthorizationError):
        forecast_stack.forecast.export_summary(
            stored.id,
            principal=writer,
            acl_epoch=forecast_stack.identity.acl_epoch(),
        )
