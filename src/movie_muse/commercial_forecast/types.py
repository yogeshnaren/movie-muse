"""Comparables, assumption sets, P10/P50/P90 traces, backtests, and sensitivity."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from movie_muse.schemas.api import ScenarioModel, ScenarioOutcome

DISCLAIMER = (
    "Commercial scenarios are not a guarantee and not a single guaranteed number. "
    "P10/P50/P90 are method-backed ranges with data dates and assumptions."
)
INSUFFICIENT_EVIDENCE = "insufficient evidence"
MODEL_VERSION = "commercial-forecast-1.0"
MIN_IN_DISTRIBUTION = 3
REQUIRED_ASSUMPTIONS: tuple[str, ...] = (
    "distribution",
    "marketing",
    "release",
    "territory",
    "talent",
    "platform",
)
FORBIDDEN_GUARANTEE_PHRASES: tuple[str, ...] = (
    "guaranteed number",
    "guaranteed return",
    "will earn",
    "highly accurate",
    "sure thing",
    "locked revenue",
)


class AssumptionKey(str, Enum):
    DISTRIBUTION = "distribution"
    MARKETING = "marketing"
    RELEASE = "release"
    TERRITORY = "territory"
    TALENT = "talent"
    PLATFORM = "platform"


@dataclass(frozen=True, slots=True)
class ComparableTitle:
    id: str
    project_id: str
    title: str
    territory: str
    platform: str
    budget: float
    observed_gross: float
    release_date: str
    data_as_of: str
    source: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "territory": self.territory,
            "platform": self.platform,
            "budget": self.budget,
            "observed_gross": self.observed_gross,
            "release_date": self.release_date,
            "data_as_of": self.data_as_of,
            "source": self.source,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComparableTitle:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            title=str(data["title"]),
            territory=str(data["territory"]),
            platform=str(data["platform"]),
            budget=float(data["budget"]),
            observed_gross=float(data["observed_gross"]),
            release_date=str(data["release_date"]),
            data_as_of=str(data["data_as_of"]),
            source=str(data["source"]),
            rationale=str(data["rationale"]),
        )


@dataclass(frozen=True, slots=True)
class ForecastAssumption:
    id: str
    project_id: str
    key: AssumptionKey
    value: str
    data_as_of: str
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "key": self.key.value,
            "value": self.value,
            "data_as_of": self.data_as_of,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ForecastAssumption:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            key=AssumptionKey(str(data["key"])),
            value=str(data["value"]),
            data_as_of=str(data["data_as_of"]),
            evidence=str(data["evidence"]),
        )


@dataclass(frozen=True, slots=True)
class NumberTrace:
    percentile: str
    value: float
    unit: str
    method: str
    data_as_of: str
    assumption_ids: tuple[str, ...]
    comparable_ids: tuple[str, ...]
    budget_id: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "percentile": self.percentile,
            "value": self.value,
            "unit": self.unit,
            "method": self.method,
            "data_as_of": self.data_as_of,
            "assumption_ids": list(self.assumption_ids),
            "comparable_ids": list(self.comparable_ids),
            "budget_id": self.budget_id,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NumberTrace:
        assumption_ids = data.get("assumption_ids", ())
        comparable_ids = data.get("comparable_ids", ())
        if not isinstance(assumption_ids, list | tuple) or not isinstance(
            comparable_ids, list | tuple
        ):
            raise ValueError("number trace ids are not lists")
        return cls(
            percentile=str(data["percentile"]),
            value=float(data["value"]),
            unit=str(data["unit"]),
            method=str(data["method"]),
            data_as_of=str(data["data_as_of"]),
            assumption_ids=tuple(str(item) for item in assumption_ids),
            comparable_ids=tuple(str(item) for item in comparable_ids),
            budget_id=str(data["budget_id"]),
            source=str(data["source"]),
        )


@dataclass(frozen=True, slots=True)
class CommercialForecast:
    scenario: ScenarioModel
    budget_id: str
    traces: tuple[NumberTrace, ...]
    comparable_ids: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    coverage: float
    insufficient: bool = False
    guarantee: bool = False
    audience_run_id: str | None = None
    input_fingerprint: str = ""
    disclaimer: str = DISCLAIMER

    @property
    def id(self) -> str:
        return self.scenario.id

    @property
    def project_id(self) -> str:
        return self.scenario.project_id

    def outcome(self, percentile: str) -> ScenarioOutcome:
        for item in self.scenario.outcomes:
            if item.percentile == percentile:
                return item
        raise KeyError(percentile)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario.to_dict(),
            "budget_id": self.budget_id,
            "traces": [item.to_dict() for item in self.traces],
            "comparable_ids": list(self.comparable_ids),
            "assumption_ids": list(self.assumption_ids),
            "coverage": self.coverage,
            "insufficient": self.insufficient,
            "guarantee": self.guarantee,
            "audience_run_id": self.audience_run_id,
            "input_fingerprint": self.input_fingerprint,
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommercialForecast:
        traces = data.get("traces", ())
        comparable_ids = data.get("comparable_ids", ())
        assumption_ids = data.get("assumption_ids", ())
        if not isinstance(traces, list | tuple):
            raise ValueError("forecast traces is not a list")
        if not isinstance(comparable_ids, list | tuple) or not isinstance(
            assumption_ids, list | tuple
        ):
            raise ValueError("forecast id lists are invalid")
        audience_run_id = data.get("audience_run_id")
        return cls(
            scenario=ScenarioModel.from_dict(dict(data["scenario"])),
            budget_id=str(data["budget_id"]),
            traces=tuple(NumberTrace.from_dict(dict(item)) for item in traces),
            comparable_ids=tuple(str(item) for item in comparable_ids),
            assumption_ids=tuple(str(item) for item in assumption_ids),
            coverage=float(data["coverage"]),
            insufficient=bool(data.get("insufficient", False)),
            guarantee=bool(data.get("guarantee", False)),
            audience_run_id=str(audience_run_id) if audience_run_id else None,
            input_fingerprint=str(data.get("input_fingerprint", "")),
            disclaimer=str(data.get("disclaimer", DISCLAIMER)),
        )


@dataclass(frozen=True, slots=True)
class BacktestReport:
    id: str
    project_id: str
    cutoff: str
    train_ids: tuple[str, ...]
    test_ids: tuple[str, ...]
    model_mae: float
    baseline_mae: float
    leakage: bool = False
    method: str = "time-split holdout vs train-mean baseline; no future data"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "cutoff": self.cutoff,
            "train_ids": list(self.train_ids),
            "test_ids": list(self.test_ids),
            "model_mae": self.model_mae,
            "baseline_mae": self.baseline_mae,
            "leakage": self.leakage,
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BacktestReport:
        train_ids = data.get("train_ids", ())
        test_ids = data.get("test_ids", ())
        if not isinstance(train_ids, list | tuple) or not isinstance(test_ids, list | tuple):
            raise ValueError("backtest id lists are invalid")
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            cutoff=str(data["cutoff"]),
            train_ids=tuple(str(item) for item in train_ids),
            test_ids=tuple(str(item) for item in test_ids),
            model_mae=float(data["model_mae"]),
            baseline_mae=float(data["baseline_mae"]),
            leakage=bool(data.get("leakage", False)),
            method=str(data.get("method", "time-split holdout vs train-mean baseline; no future data")),
        )


@dataclass(frozen=True, slots=True)
class SensitivityReport:
    id: str
    forecast_id: str
    assumption_key: str
    delta: str
    base_p50: float
    shocked_p50: float
    method: str
    data_as_of: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "forecast_id": self.forecast_id,
            "assumption_key": self.assumption_key,
            "delta": self.delta,
            "base_p50": self.base_p50,
            "shocked_p50": self.shocked_p50,
            "method": self.method,
            "data_as_of": self.data_as_of,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SensitivityReport:
        return cls(
            id=str(data["id"]),
            forecast_id=str(data["forecast_id"]),
            assumption_key=str(data["assumption_key"]),
            delta=str(data["delta"]),
            base_p50=float(data["base_p50"]),
            shocked_p50=float(data["shocked_p50"]),
            method=str(data["method"]),
            data_as_of=str(data["data_as_of"]),
        )
