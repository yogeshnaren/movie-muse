"""P10/P50/P90 commercial scenarios. Ranges are not a single guaranteed number."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from statistics import fmean
from typing import Any

from movie_muse.audience_lab.api import AudienceLabService, EvidenceTier, assert_no_population_claim
from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.budget.api import BudgetService, StaleBudgetError, StoredBudget
from movie_muse.commercial_forecast.errors import (
    AssumptionError,
    ForecastNotFoundError,
    GuaranteeClaimError,
    InsufficientEvidenceError,
    LeakageError,
    UntracedNumberError,
)
from movie_muse.commercial_forecast.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.commercial_forecast.types import (
    DISCLAIMER,
    FORBIDDEN_GUARANTEE_PHRASES,
    INSUFFICIENT_EVIDENCE,
    MIN_IN_DISTRIBUTION,
    MODEL_VERSION,
    REQUIRED_ASSUMPTIONS,
    AssumptionKey,
    BacktestReport,
    CommercialForecast,
    ComparableTitle,
    ForecastAssumption,
    NumberTrace,
    SensitivityReport,
)
from movie_muse.identity.api import IdentityService, Principal
from movie_muse.persistence.api import LocalWorkspace, digest_payload, utc_now
from movie_muse.schemas.api import ScenarioModel, ScenarioOutcome, new_id, new_ulid


def assert_no_guarantee(text: str) -> str:
    lowered = f" {text.lower()} "
    for phrase in FORBIDDEN_GUARANTEE_PHRASES:
        start = 0
        while True:
            found = lowered.find(phrase, start)
            if found < 0:
                break
            prefix = lowered[max(0, found - 32) : found]
            negated = any(
                marker in prefix for marker in (" not ", " never ", " not a ", " not an ")
            )
            if not negated:
                raise GuaranteeClaimError(
                    f"commercial text must not claim a guaranteed outcome: {phrase}"
                )
            start = found + 1
    return text


def _percentile(sorted_values: Sequence[float], fraction: float) -> float:
    if not sorted_values:
        raise InsufficientEvidenceError(INSUFFICIENT_EVIDENCE)
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    position = fraction * (len(sorted_values) - 1)
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    weight = position - low
    return round(sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight, 2)


class CommercialForecastService:
    """Comparables-backed P10/P50/P90 ranges with time-split backtests."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        identity: IdentityService,
        audit: AuditLog,
        budgets: BudgetService,
        lab: AudienceLabService,
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.identity = identity
        self.audit = audit
        self.budgets = budgets
        self.lab = lab
        self.clock = clock

    def register_comparable(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        title: str,
        territory: str,
        platform: str,
        budget: float,
        observed_gross: float,
        release_date: str,
        data_as_of: str,
        source: str,
        rationale: str,
    ) -> ComparableTitle:
        self._require_financial(principal, project_id, acl_epoch)
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        cleaned = assert_no_guarantee(rationale.strip())
        if not cleaned or not source.strip() or not data_as_of.strip():
            raise UntracedNumberError("comparables need rationale, source, and a data date")
        if release_date > data_as_of:
            raise LeakageError("comparable data_as_of cannot precede its release_date")
        item = ComparableTitle(
            id=f"cmp_{new_ulid()}",
            project_id=project_id,
            title=title.strip(),
            territory=territory.strip(),
            platform=platform.strip(),
            budget=float(budget),
            observed_gross=float(observed_gross),
            release_date=release_date,
            data_as_of=data_as_of,
            source=source.strip(),
            rationale=cleaned,
        )
        written = self._put_comparable(item)
        self._audit(principal, acl_epoch, "forecast.comparable", written.id, written.title)
        return written

    def set_assumption(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        key: AssumptionKey | str,
        value: str,
        data_as_of: str,
        evidence: str,
    ) -> ForecastAssumption:
        self._require_financial(principal, project_id, acl_epoch)
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        parsed = key if isinstance(key, AssumptionKey) else AssumptionKey(str(key))
        cleaned_value = assert_no_guarantee(value.strip())
        cleaned_evidence = evidence.strip()
        if not cleaned_value or not cleaned_evidence or not data_as_of.strip():
            raise AssumptionError("assumptions need a value, evidence, and data date")
        item = ForecastAssumption(
            id=f"csa_{new_ulid()}",
            project_id=project_id,
            key=parsed,
            value=cleaned_value,
            data_as_of=data_as_of,
            evidence=cleaned_evidence,
        )
        written = self._put_assumption(item)
        self._audit(principal, acl_epoch, "forecast.assumption", written.id, parsed.value)
        return written

    def forecast(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        budget_id: str,
        as_of: str,
        audience_run_id: str | None = None,
    ) -> CommercialForecast:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        budget = self.budgets.get_budget(budget_id, principal=principal, acl_epoch=acl_epoch)
        if budget.project_id != project_id:
            raise InsufficientEvidenceError("budget project does not match the forecast project")
        if budget.labeled_stale or budget.projection.is_stale:
            raise StaleBudgetError("stale budget cannot back a current commercial scenario")
        assumptions = self._required_assumptions(project_id)
        territory = assumptions[AssumptionKey.TERRITORY].value
        platform = assumptions[AssumptionKey.PLATFORM].value
        comparables = self._select_comparables(project_id, as_of, territory, platform)
        coverage = round(len(comparables) / MIN_IN_DISTRIBUTION, 6)
        audience_note = ""
        audience_factor = 1.0
        if audience_run_id:
            run = self.lab.get_run(
                audience_run_id, principal=principal, acl_epoch=acl_epoch
            )
            if run.project_id != project_id:
                raise InsufficientEvidenceError("audience run project does not match")
            assert_no_population_claim(run.disclaimer)
            if run.tier is EvidenceTier.SYNTHETIC_LLM:
                audience_note = (
                    " Synthetic audience mean is a labeled hypothesis, not a population."
                )
            audience_factor = round(0.85 + 0.3 * run.mean_score, 6)
        _, fingerprint = digest_payload(
            {
                "budget_id": budget.id,
                "as_of": as_of,
                "territory": territory,
                "platform": platform,
                "comparable_ids": [item.id for item in comparables],
                "assumption_ids": [item.id for item in assumptions.values()],
                "audience_run_id": audience_run_id or "",
                "audience_factor": audience_factor,
            }
        )
        reused = self._forecast_for_fingerprint(project_id, fingerprint)
        if reused is not None:
            self._audit(principal, acl_epoch, "forecast.repeat", reused.id, fingerprint)
            return reused
        scaled = self._scaled_grosses(comparables, budget)
        scaled = tuple(round(value * audience_factor, 2) for value in scaled)
        method = (
            "time-aware comparable ratio to current budget; interpolated P10/P50/P90; "
            "not a single guaranteed number."
            + audience_note
        )
        method = assert_no_guarantee(method)
        p10 = _percentile(scaled, 0.1)
        p50 = _percentile(scaled, 0.5)
        p90 = _percentile(scaled, 0.9)
        assumption_ids = tuple(item.id for item in assumptions.values())
        comparable_ids = tuple(item.id for item in comparables)
        traces = tuple(
            self._trace(percentile, value, method, as_of, assumption_ids, comparable_ids, budget)
            for percentile, value in (("P10", p10), ("P50", p50), ("P90", p90))
        )
        scenario = ScenarioModel(
            id=new_id("scenario_model"),
            project_id=project_id,
            methodology_summary=method,
            model_version=MODEL_VERSION,
            data_as_of=as_of,
            computed_at=self.clock(),
            outcomes=(
                ScenarioOutcome(percentile="P10", value=p10, unit=budget.currency),
                ScenarioOutcome(percentile="P50", value=p50, unit=budget.currency),
                ScenarioOutcome(percentile="P90", value=p90, unit=budget.currency),
            ),
            assumptions=tuple(f"{item.key.value}={item.value}" for item in assumptions.values()),
            comparables=comparable_ids,
            uncertainty_notes=DISCLAIMER,
            is_out_of_distribution=False,
        )
        stored = CommercialForecast(
            scenario=scenario,
            budget_id=budget.id,
            traces=traces,
            comparable_ids=comparable_ids,
            assumption_ids=assumption_ids,
            coverage=coverage,
            insufficient=False,
            guarantee=False,
            audience_run_id=audience_run_id,
            input_fingerprint=fingerprint,
        )
        written = self._put_forecast(stored)
        self._audit(principal, acl_epoch, "forecast.compile", written.id, as_of)
        return written

    def backtest(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        cutoff: str,
    ) -> BacktestReport:
        self._require_financial(principal, project_id, acl_epoch)
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        comps = self._comparables_for(project_id)
        train = [item for item in comps if item.release_date < cutoff]
        test = [item for item in comps if item.release_date >= cutoff]
        leaked = [item for item in train if item.data_as_of > cutoff]
        if leaked:
            raise LeakageError("train split contains data dated after the cutoff")
        future_in_train = [item for item in train if item.release_date >= cutoff]
        if future_in_train:
            raise LeakageError("train split contains post-cutoff releases")
        if len(train) < MIN_IN_DISTRIBUTION or not test:
            raise InsufficientEvidenceError(INSUFFICIENT_EVIDENCE)
        baseline = fmean(item.observed_gross for item in train)
        model_errors: list[float] = []
        baseline_errors: list[float] = []
        for held in test:
            peers = [
                item
                for item in train
                if item.territory == held.territory and item.platform == held.platform
            ]
            if len(peers) < MIN_IN_DISTRIBUTION:
                raise InsufficientEvidenceError(INSUFFICIENT_EVIDENCE)
            scaled = []
            for peer in peers:
                ratio = held.budget / peer.budget if peer.budget else 1.0
                scaled.append(peer.observed_gross * ratio)
            scaled.sort()
            predicted = _percentile(scaled, 0.5)
            model_errors.append(abs(predicted - held.observed_gross))
            baseline_errors.append(abs(baseline - held.observed_gross))
        report = BacktestReport(
            id=f"bkt_{new_ulid()}",
            project_id=project_id,
            cutoff=cutoff,
            train_ids=tuple(item.id for item in train),
            test_ids=tuple(item.id for item in test),
            model_mae=round(fmean(model_errors), 2),
            baseline_mae=round(fmean(baseline_errors), 2),
            leakage=False,
        )
        written = self._put_backtest(report)
        self._audit(principal, acl_epoch, "forecast.backtest", written.id, cutoff)
        return written

    def sensitivity(
        self,
        forecast_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        assumption_key: AssumptionKey | str,
        delta: float,
    ) -> SensitivityReport:
        stored = self.get_forecast(forecast_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        parsed = (
            assumption_key
            if isinstance(assumption_key, AssumptionKey)
            else AssumptionKey(str(assumption_key))
        )
        if parsed not in {AssumptionKey.MARKETING, AssumptionKey.DISTRIBUTION}:
            raise AssumptionError("sensitivity applies to marketing or distribution intensity")
        base = stored.outcome("P50").value
        factor = 1.0 + float(delta)
        shocked = round(base * factor, 2)
        report = SensitivityReport(
            id=f"sns_{new_ulid()}",
            forecast_id=stored.id,
            assumption_key=parsed.value,
            delta=str(delta),
            base_p50=base,
            shocked_p50=shocked,
            method=(
                f"one-at-a-time {parsed.value} intensity shock {delta}; "
                "not a guaranteed outcome"
            ),
            data_as_of=stored.scenario.data_as_of,
        )
        written = self._put_sensitivity(report)
        self._audit(principal, acl_epoch, "forecast.sensitivity", written.id, parsed.value)
        return written

    def export_summary(
        self, forecast_id: str, *, principal: Principal, acl_epoch: int
    ) -> str:
        stored = self.get_forecast(forecast_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.EXPORT, stored.project_id, acl_epoch)
        if stored.guarantee or stored.insufficient:
            raise GuaranteeClaimError("export refuses guaranteed or insufficient scenarios")
        parts = [
            stored.disclaimer,
            DISCLAIMER,
            f"SCENARIO {stored.id} VERSION {stored.scenario.model_version}",
            f"DATA_AS_OF {stored.scenario.data_as_of}",
            f"BUDGET {stored.budget_id} COVERAGE {stored.coverage}",
            stored.scenario.methodology_summary,
        ]
        for trace in stored.traces:
            parts.append(
                f"{trace.percentile}={trace.value} {trace.unit} method={trace.method} "
                f"data_as_of={trace.data_as_of} comps={','.join(trace.comparable_ids)} "
                f"assumptions={','.join(trace.assumption_ids)}"
            )
        text = "\n".join(parts)
        return assert_no_guarantee(text)

    def get_forecast(
        self, forecast_id: str, *, principal: Principal, acl_epoch: int
    ) -> CommercialForecast:
        stored = self._load_forecast(forecast_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        self._require_financial(principal, stored.project_id, acl_epoch)
        return stored

    def list_forecasts(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[CommercialForecast, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        self._require_financial(principal, project_id, acl_epoch)
        index = load_index(self.workspace)
        ids = list(dict(dict(index.get("by_project", {})).get(project_id, {})).get("forecasts", []))
        found: list[CommercialForecast] = []
        for forecast_id in ids:
            digest = dict(index.get("forecast_digests", {})).get(str(forecast_id))
            if digest is None:
                continue
            found.append(CommercialForecast.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(found)

    def _required_assumptions(self, project_id: str) -> dict[AssumptionKey, ForecastAssumption]:
        latest: dict[AssumptionKey, ForecastAssumption] = {}
        for item in self._assumptions_for(project_id):
            latest[item.key] = item
        missing = [key for key in REQUIRED_ASSUMPTIONS if AssumptionKey(key) not in latest]
        if missing:
            raise AssumptionError(
                f"missing required assumptions: {', '.join(missing)}"
            )
        return latest

    def _select_comparables(
        self,
        project_id: str,
        as_of: str,
        territory: str,
        platform: str,
    ) -> tuple[ComparableTitle, ...]:
        selected: list[ComparableTitle] = []
        for item in self._comparables_for(project_id):
            if item.data_as_of > as_of or item.release_date > as_of:
                continue
            if item.territory != territory or item.platform != platform:
                continue
            if not item.rationale or not item.source:
                raise UntracedNumberError("selected comparable is missing rationale or source")
            selected.append(item)
        if len(selected) < MIN_IN_DISTRIBUTION:
            raise InsufficientEvidenceError(INSUFFICIENT_EVIDENCE)
        return tuple(selected)

    def _scaled_grosses(
        self, comparables: Sequence[ComparableTitle], budget: StoredBudget
    ) -> tuple[float, ...]:
        subject = float(budget.total)
        values: list[float] = []
        for item in comparables:
            if item.budget <= 0:
                raise UntracedNumberError("comparable budget must be positive")
            values.append(item.observed_gross * (subject / item.budget))
        values.sort()
        return tuple(values)

    def _trace(
        self,
        percentile: str,
        value: float,
        method: str,
        as_of: str,
        assumption_ids: tuple[str, ...],
        comparable_ids: tuple[str, ...],
        budget: StoredBudget,
    ) -> NumberTrace:
        if not method or not as_of or not assumption_ids or not comparable_ids:
            raise UntracedNumberError("every number must link to data, method, and assumptions")
        return NumberTrace(
            percentile=percentile,
            value=value,
            unit=budget.currency,
            method=method,
            data_as_of=as_of,
            assumption_ids=assumption_ids,
            comparable_ids=comparable_ids,
            budget_id=budget.id,
            source="comparables+budget",
        )

    def _comparables_for(self, project_id: str) -> tuple[ComparableTitle, ...]:
        index = load_index(self.workspace)
        ids = list(dict(dict(index.get("by_project", {})).get(project_id, {})).get("comparables", []))
        found: list[ComparableTitle] = []
        for item_id in ids:
            digest = dict(index.get("comparable_digests", {})).get(str(item_id))
            if digest is None:
                continue
            found.append(ComparableTitle.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(found)

    def _assumptions_for(self, project_id: str) -> tuple[ForecastAssumption, ...]:
        index = load_index(self.workspace)
        ids = list(dict(dict(index.get("by_project", {})).get(project_id, {})).get("assumptions", []))
        found: list[ForecastAssumption] = []
        for item_id in ids:
            digest = dict(index.get("assumption_digests", {})).get(str(item_id))
            if digest is None:
                continue
            found.append(ForecastAssumption.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(found)

    def _forecast_for_fingerprint(
        self, project_id: str, fingerprint: str
    ) -> CommercialForecast | None:
        index = load_index(self.workspace)
        forecast_id = dict(index.get("by_fingerprint", {})).get(fingerprint)
        if forecast_id is None:
            return None
        digest = dict(index.get("forecast_digests", {})).get(str(forecast_id))
        if digest is None:
            return None
        stored = CommercialForecast.from_dict(load_payload(self.workspace, str(digest)))
        if stored.project_id != project_id:
            return None
        return stored

    def _load_forecast(self, forecast_id: str) -> CommercialForecast:
        index = load_index(self.workspace)
        digest = dict(index.get("forecast_digests", {})).get(forecast_id)
        if digest is None:
            raise ForecastNotFoundError(f"forecast {forecast_id} is not in the index")
        return CommercialForecast.from_dict(load_payload(self.workspace, str(digest)))

    def _put_comparable(self, stored: ComparableTitle) -> ComparableTitle:
        def persist(index: dict[str, Any]) -> ComparableTitle:
            digest = put_payload(self.workspace, stored.to_dict())
            self._append_id(index, "comparable_ids", stored.id)
            digests = dict(index.get("comparable_digests", {}))
            digests[stored.id] = digest
            index["comparable_digests"] = digests
            self._project_bucket(index, stored.project_id, "comparables", stored.id)
            return stored

        return mutate_index(self.workspace, persist)

    def _put_assumption(self, stored: ForecastAssumption) -> ForecastAssumption:
        def persist(index: dict[str, Any]) -> ForecastAssumption:
            digest = put_payload(self.workspace, stored.to_dict())
            self._append_id(index, "assumption_ids", stored.id)
            digests = dict(index.get("assumption_digests", {}))
            digests[stored.id] = digest
            index["assumption_digests"] = digests
            self._project_bucket(index, stored.project_id, "assumptions", stored.id)
            return stored

        return mutate_index(self.workspace, persist)

    def _put_forecast(self, stored: CommercialForecast) -> CommercialForecast:
        def persist(index: dict[str, Any]) -> CommercialForecast:
            digest = put_payload(self.workspace, stored.to_dict())
            self._append_id(index, "forecast_ids", stored.id)
            digests = dict(index.get("forecast_digests", {}))
            digests[stored.id] = digest
            index["forecast_digests"] = digests
            fingerprints = dict(index.get("by_fingerprint", {}))
            fingerprints[stored.input_fingerprint] = stored.id
            index["by_fingerprint"] = fingerprints
            self._project_bucket(index, stored.project_id, "forecasts", stored.id)
            return stored

        return mutate_index(self.workspace, persist)

    def _put_backtest(self, stored: BacktestReport) -> BacktestReport:
        def persist(index: dict[str, Any]) -> BacktestReport:
            digest = put_payload(self.workspace, stored.to_dict())
            self._append_id(index, "backtest_ids", stored.id)
            digests = dict(index.get("backtest_digests", {}))
            digests[stored.id] = digest
            index["backtest_digests"] = digests
            self._project_bucket(index, stored.project_id, "backtests", stored.id)
            return stored

        return mutate_index(self.workspace, persist)

    def _put_sensitivity(self, stored: SensitivityReport) -> SensitivityReport:
        def persist(index: dict[str, Any]) -> SensitivityReport:
            digest = put_payload(self.workspace, stored.to_dict())
            self._append_id(index, "sensitivity_ids", stored.id)
            digests = dict(index.get("sensitivity_digests", {}))
            digests[stored.id] = digest
            index["sensitivity_digests"] = digests
            return stored

        return mutate_index(self.workspace, persist)

    def _append_id(self, index: dict[str, Any], key: str, item_id: str) -> None:
        ids = list(index.get(key, []))
        if item_id not in ids:
            ids.append(item_id)
        index[key] = ids

    def _project_bucket(
        self, index: dict[str, Any], project_id: str, key: str, item_id: str
    ) -> None:
        by_project = dict(index.get("by_project", {}))
        bucket = dict(by_project.get(project_id, {}))
        items = list(bucket.get(key, []))
        if item_id not in items:
            items.append(item_id)
        bucket[key] = items
        by_project[project_id] = bucket
        index["by_project"] = by_project

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )

    def _require_financial(self, principal: Principal, project_id: str, acl_epoch: int) -> None:
        self.authorization.require(
            principal,
            Action.VIEW_SENSITIVE_FINANCIAL,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )

    def _audit(
        self,
        principal: Principal,
        acl_epoch: int,
        operation: str,
        object_id: str,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="commercial_forecast",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
