"""Budget evidence ledger over a current schedule. Amounts are formula or evidenced."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.budget.engine import (
    ACCURACY_PHRASES,
    DEFAULT_CHART,
    apply_rate_delta,
    calibrate,
    estimate_amount,
    formula_amount,
    reconcile,
    require_backed,
)
from movie_muse.budget.errors import (
    AccuracyClaimError,
    BudgetNotFoundError,
    ScheduleRequiredError,
    StaleBudgetError,
    UnbackedAmountError,
)
from movie_muse.budget.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.budget.money import ZERO, parse_money, round_money
from movie_muse.budget.types import (
    ActualEntry,
    AmountEvidence,
    Assumption,
    BudgetClass,
    BudgetScenario,
    CalibrationReport,
    CommitmentEntry,
    LedgerLine,
    LineOrigin,
    StoredBudget,
)
from movie_muse.dependencies.api import DependencyEngine, NodeKind, NodeState
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.scheduling.api import ScheduleService, StaleScheduleError, StoredSchedule
from movie_muse.schemas.api import (
    BudgetMaturity,
    ProductionProjection,
    ProjectionKind,
    new_id,
    new_ulid,
)

DEFAULT_DAY_RATE = Decimal("8500.00")
DEFAULT_MOVE_RATE = Decimal("1200.00")
DEFAULT_CAST_RATE = Decimal("2500.00")
DEFAULT_FRINGE = Decimal("0.2500")
DEFAULT_CONTINGENCY = Decimal("0.1000")


class BudgetService:
    """Compile a formula-backed ledger from a current schedule. Schedule changes stale it."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        schedules: ScheduleService,
        *,
        dependencies: DependencyEngine | None = None,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.schedules = schedules
        self.dependencies = dependencies
        self.clock = clock

    def compile(
        self,
        schedule_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        maturity: BudgetMaturity | str = BudgetMaturity.PRELIMINARY_PRODUCTION_ESTIMATE,
        currency: str = "USD",
        territory: str = "US",
        contingency_rate: Decimal | str = DEFAULT_CONTINGENCY,
        incentive: Decimal | str | None = None,
        budget_id: str | None = None,
    ) -> StoredBudget:
        schedule = self.schedules.get_schedule(
            schedule_id, principal=principal, acl_epoch=acl_epoch
        )
        self._require(principal, Action.PROPOSE, schedule.project_id, acl_epoch)
        self._require_financial(principal, schedule.project_id, acl_epoch)
        if schedule.labeled_stale or schedule.projection.is_stale:
            raise ScheduleRequiredError("a current schedule must precede the budget")
        parsed_maturity = (
            maturity if isinstance(maturity, BudgetMaturity) else BudgetMaturity(str(maturity))
        )
        existing = (
            self.get_budget(budget_id, principal=principal, acl_epoch=acl_epoch)
            if budget_id
            else None
        )
        evidence = AmountEvidence(
            source="internal unit rate card",
            as_of_date=self.clock()[:10],
            territory=territory,
            currency=currency,
            note="declared production unit rates; not a bid",
        )
        lines = list(
            self._schedule_lines(schedule, currency=currency, evidence=evidence)
        )
        production = round_money(
            sum((item.amount for item in lines), ZERO), currency=currency
        )
        contingent, formula = formula_amount(
            quantity=production,
            rate=parse_money(contingency_rate),
            fringe_rate=ZERO,
            currency=currency,
        )
        lines.append(
            LedgerLine(
                id=f"bln_{new_ulid()}",
                account_code="3100",
                origin=LineOrigin.FORMULA,
                quantity=production,
                rate=parse_money(contingency_rate),
                unit="currency",
                fringe_rate=ZERO,
                amount=contingent,
                currency=currency,
                evidence=evidence,
                formula=formula,
                department="producer",
                geography=territory,
                budget_class=BudgetClass.CONTINGENCY,
            )
        )
        if incentive is not None:
            credit = estimate_amount(parse_money(incentive), evidence, currency)
            if credit > ZERO:
                credit = round_money(ZERO - credit, currency=currency)
            lines.append(
                LedgerLine(
                    id=f"bln_{new_ulid()}",
                    account_code="4100",
                    origin=LineOrigin.ESTIMATE,
                    quantity=Decimal("1"),
                    rate=credit,
                    unit="lump",
                    fringe_rate=ZERO,
                    amount=credit,
                    currency=currency,
                    evidence=evidence,
                    formula="explicit incentive estimate",
                    department="producer",
                    geography=territory,
                    budget_class=BudgetClass.INCENTIVE,
                )
            )
        for line in lines:
            require_backed(line)
        total = round_money(sum((item.amount for item in lines), ZERO), currency=currency)
        reconcile(lines, total, currency)
        actuals = existing.actuals if existing else ()
        commitments = existing.commitments if existing else ()
        calibration = calibrate(
            maturity=parsed_maturity,
            lines=lines,
            actuals=actuals,
            currency=currency,
        )
        projection_id = existing.projection.id if existing else new_id("production_projection")
        stored = StoredBudget(
            projection=ProductionProjection(
                id=projection_id,
                project_id=schedule.project_id,
                kind=ProjectionKind.BUDGET_EVIDENCE,
                source_revision_id=schedule.projection.source_revision_id,
                computed_at=self.clock(),
                data={
                    "schedule_id": schedule.id,
                    "line_count": len(lines),
                    "total": format(total, "f"),
                },
                is_stale=False,
                budget_maturity=parsed_maturity,
            ),
            schedule_id=schedule.id,
            currency=currency,
            accounts=DEFAULT_CHART,
            lines=tuple(lines),
            assumptions=self._assumptions(evidence, contingency_rate),
            actuals=actuals,
            commitments=commitments,
            total=total,
            calibration=calibration,
            labeled_stale=False,
            config_node_id=existing.config_node_id if existing else None,
            analysis_node_id=existing.analysis_node_id if existing else None,
        )
        written = self._put(stored)
        if written.config_node_id is None:
            written = self._attach_dependency_nodes(written, principal, acl_epoch)
        self._audit(principal, acl_epoch, "budget.compile", written.id, parsed_maturity.value)
        return written

    def get_budget(
        self, budget_id: str, *, principal: Principal, acl_epoch: int
    ) -> StoredBudget:
        stored = self._load(budget_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        self._require_financial(principal, stored.project_id, acl_epoch)
        return self._with_freshness(stored, principal, acl_epoch)

    def override_line(
        self,
        budget_id: str,
        line_id: str,
        amount: Decimal | str,
        evidence: AmountEvidence,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredBudget:
        stored = self.get_budget(budget_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        rounded = estimate_amount(parse_money(amount), evidence, stored.currency)
        lines: list[LedgerLine] = []
        found = False
        for line in stored.lines:
            if line.id != line_id:
                lines.append(line)
                continue
            found = True
            lines.append(
                LedgerLine(
                    id=line.id,
                    account_code=line.account_code,
                    origin=LineOrigin.OVERRIDE,
                    quantity=Decimal("1"),
                    rate=rounded,
                    unit="lump",
                    fringe_rate=ZERO,
                    amount=rounded,
                    currency=stored.currency,
                    evidence=evidence,
                    formula="explicit override",
                    department=line.department,
                    geography=line.geography,
                    budget_class=line.budget_class,
                    assumption_id=line.assumption_id,
                )
            )
        if not found:
            raise UnbackedAmountError(f"line {line_id} is not on budget {budget_id}")
        return self._rewrite_lines(stored, lines, principal, acl_epoch, "budget.override")

    def add_actual(
        self,
        budget_id: str,
        line_id: str,
        amount: Decimal | str,
        evidence: AmountEvidence,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredBudget:
        stored = self.get_budget(budget_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        self._line(stored, line_id)
        entry = ActualEntry(
            id=f"bxa_{new_ulid()}",
            line_id=line_id,
            amount=estimate_amount(parse_money(amount), evidence, stored.currency),
            currency=stored.currency,
            evidence=evidence,
        )
        updated = self._clone(stored, actuals=stored.actuals + (entry,))
        written = self._put(updated)
        self._audit(principal, acl_epoch, "budget.actual", written.id, line_id)
        return written

    def add_commitment(
        self,
        budget_id: str,
        line_id: str,
        amount: Decimal | str,
        evidence: AmountEvidence,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredBudget:
        stored = self.get_budget(budget_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        self._line(stored, line_id)
        entry = CommitmentEntry(
            id=f"bcm_{new_ulid()}",
            line_id=line_id,
            amount=estimate_amount(parse_money(amount), evidence, stored.currency),
            currency=stored.currency,
            evidence=evidence,
        )
        updated = self._clone(stored, commitments=stored.commitments + (entry,))
        written = self._put(updated)
        self._audit(principal, acl_epoch, "budget.commitment", written.id, line_id)
        return written

    def sensitivity(
        self,
        budget_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        rate_delta: Decimal | str,
        label: str,
    ) -> BudgetScenario:
        stored = self.get_budget(budget_id, principal=principal, acl_epoch=acl_epoch)
        delta = parse_money(rate_delta)
        total = apply_rate_delta(stored.lines, delta, stored.currency)
        scenario = BudgetScenario(
            id=new_id("scenario_model"),
            label=label,
            seed=0,
            rate_delta=delta,
            total=total,
            currency=stored.currency,
        )
        self._audit(principal, acl_epoch, "budget.sensitivity", stored.id, label)
        return scenario

    def claim_accuracy(
        self,
        budget_id: str,
        phrase: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> CalibrationReport:
        stored = self.get_budget(budget_id, principal=principal, acl_epoch=acl_epoch)
        lowered = phrase.casefold()
        if any(token in lowered for token in ACCURACY_PHRASES) and not stored.calibration.validated:
            raise AccuracyClaimError(
                "the ledger is not validated as extremely accurate at this maturity"
            )
        return stored.calibration

    def export_ledger(
        self, budget_id: str, *, principal: Principal, acl_epoch: int
    ) -> str:
        stored = self.get_budget(budget_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.EXPORT, stored.project_id, acl_epoch)
        if stored.labeled_stale or stored.projection.is_stale:
            raise StaleBudgetError("stale budget cannot be exported as current")
        lines = [
            f"BUDGET {stored.id}",
            f"MATURITY {stored.maturity.value}",
            f"CURRENCY {stored.currency}",
            f"TOTAL {format(stored.total, 'f')}",
            stored.calibration.disclaimer,
        ]
        for line in stored.lines:
            lines.append(
                f"{line.account_code}\t{format(line.amount, 'f')}\t{line.origin.value}\t"
                f"{line.formula}"
            )
        self._audit(principal, acl_epoch, "budget.export", stored.id, stored.maturity.value)
        return "\n".join(lines)

    def notify_schedule_changed(
        self,
        schedule_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[str, ...]:
        index = load_index(self.workspace)
        budget_ids = list(dict(index.get("by_schedule", {})).get(schedule_id, []))
        stale_ids: list[str] = []
        for budget_id in budget_ids:
            stored = self.get_budget(budget_id, principal=principal, acl_epoch=acl_epoch)
            if self.dependencies is not None and stored.config_node_id:
                self.dependencies.invalidate_inputs(
                    [stored.config_node_id],
                    principal=principal,
                    acl_epoch=acl_epoch,
                )
            marked = self._put(self._with_projection_stale(stored, stale=True))
            stale_ids.append(marked.id)
        self._audit(
            principal,
            acl_epoch,
            "budget.notify_schedule_changed",
            schedule_id,
            ",".join(stale_ids),
        )
        return tuple(stale_ids)

    def _schedule_lines(
        self,
        schedule: StoredSchedule,
        *,
        currency: str,
        evidence: AmountEvidence,
    ) -> tuple[LedgerLine, ...]:
        shooting_days = max(1, len(schedule.boards))
        moves = sum(
            1
            for board in schedule.boards
            for strip in board.strips
            if strip.company_move_minutes > 0
        )
        cast_names = sorted(
            {
                name
                for board in schedule.boards
                for strip in board.strips
                for name in strip.scene.cast
            }
        )
        specs = (
            ("1100", Decimal(len(cast_names) or 1), DEFAULT_CAST_RATE, "cast-day", "casting", BudgetClass.LABOR),
            ("2100", Decimal(shooting_days), DEFAULT_DAY_RATE, "day", "ad", BudgetClass.LABOR),
            ("2200", Decimal(moves), DEFAULT_MOVE_RATE, "move", "locations", BudgetClass.LOCATION),
        )
        lines: list[LedgerLine] = []
        for code, quantity, rate, unit, department, budget_class in specs:
            amount, formula = formula_amount(
                quantity=quantity,
                rate=rate,
                fringe_rate=DEFAULT_FRINGE if budget_class is BudgetClass.LABOR else ZERO,
                currency=currency,
            )
            lines.append(
                LedgerLine(
                    id=f"bln_{new_ulid()}",
                    account_code=code,
                    origin=LineOrigin.SCHEDULE,
                    quantity=quantity,
                    rate=rate,
                    unit=unit,
                    fringe_rate=DEFAULT_FRINGE if budget_class is BudgetClass.LABOR else ZERO,
                    amount=amount,
                    currency=currency,
                    evidence=evidence,
                    formula=formula,
                    department=department,
                    geography=evidence.territory,
                    budget_class=budget_class,
                )
            )
        return tuple(lines)

    def _assumptions(
        self, evidence: AmountEvidence, contingency_rate: Decimal | str
    ) -> tuple[Assumption, ...]:
        return (
            Assumption(
                id=f"bas_{new_ulid()}",
                key="day_rate",
                value=format(DEFAULT_DAY_RATE, "f"),
                evidence=evidence,
            ),
            Assumption(
                id=f"bas_{new_ulid()}",
                key="contingency_rate",
                value=format(parse_money(contingency_rate), "f"),
                evidence=evidence,
            ),
        )

    def _rewrite_lines(
        self,
        stored: StoredBudget,
        lines: Sequence[LedgerLine],
        principal: Principal,
        acl_epoch: int,
        operation: str,
    ) -> StoredBudget:
        for line in lines:
            require_backed(line)
        total = round_money(sum((item.amount for item in lines), ZERO), currency=stored.currency)
        reconcile(lines, total, stored.currency)
        calibration = calibrate(
            maturity=stored.maturity,
            lines=lines,
            actuals=stored.actuals,
            currency=stored.currency,
        )
        updated = self._clone(stored, lines=tuple(lines), total=total, calibration=calibration)
        written = self._put(updated)
        self._audit(principal, acl_epoch, operation, written.id, str(len(lines)))
        return written

    def _line(self, stored: StoredBudget, line_id: str) -> LedgerLine:
        for line in stored.lines:
            if line.id == line_id:
                return line
        raise UnbackedAmountError(f"line {line_id} is not on budget {stored.id}")

    def _load(self, budget_id: str) -> StoredBudget:
        index = load_index(self.workspace)
        digest = dict(index.get("budget_digests", {})).get(budget_id)
        if digest is None:
            raise BudgetNotFoundError(f"budget {budget_id} is not in the index")
        return StoredBudget.from_dict(load_payload(self.workspace, str(digest)))

    def _put(self, stored: StoredBudget) -> StoredBudget:
        def persist(index: dict[str, Any]) -> StoredBudget:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("budget_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["budget_ids"] = ids
            digests = dict(index.get("budget_digests", {}))
            digests[stored.id] = digest
            index["budget_digests"] = digests
            by_project = dict(index.get("by_project", {}))
            project_ids = list(by_project.get(stored.project_id, []))
            if stored.id not in project_ids:
                project_ids.append(stored.id)
            by_project[stored.project_id] = project_ids
            index["by_project"] = by_project
            by_schedule = dict(index.get("by_schedule", {}))
            schedule_ids = list(by_schedule.get(stored.schedule_id, []))
            if stored.id not in schedule_ids:
                schedule_ids.append(stored.id)
            by_schedule[stored.schedule_id] = schedule_ids
            index["by_schedule"] = by_schedule
            return stored

        return mutate_index(self.workspace, persist)

    def _attach_dependency_nodes(
        self,
        stored: StoredBudget,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredBudget:
        if self.dependencies is None:
            return stored
        config = self.dependencies.add_node(
            project_id=stored.project_id,
            kind=NodeKind.CONFIGURATION,
            principal=principal,
            acl_epoch=acl_epoch,
            subject_id=stored.id,
        )
        analysis = self.dependencies.add_node(
            project_id=stored.project_id,
            kind=NodeKind.DERIVED_PROJECTION,
            principal=principal,
            acl_epoch=acl_epoch,
            input_ids=(config.id,),
            subject_id=stored.id,
        )
        updated = self._clone(
            stored, config_node_id=config.id, analysis_node_id=analysis.id
        )
        return self._put(updated)

    def _with_freshness(
        self, stored: StoredBudget, principal: Principal, acl_epoch: int
    ) -> StoredBudget:
        labeled = stored.labeled_stale
        if self.dependencies is not None and stored.analysis_node_id:
            view = self.dependencies.view_node(
                stored.analysis_node_id, principal=principal, acl_epoch=acl_epoch
            )
            labeled = labeled or view.state is NodeState.STALE
        try:
            schedule = self.schedules.get_schedule(
                stored.schedule_id, principal=principal, acl_epoch=acl_epoch
            )
            labeled = labeled or schedule.labeled_stale or schedule.projection.is_stale
        except StaleScheduleError:
            labeled = True
        if labeled == stored.labeled_stale and stored.projection.is_stale == labeled:
            return stored
        return self._with_projection_stale(stored, stale=labeled)

    def _with_projection_stale(self, stored: StoredBudget, *, stale: bool) -> StoredBudget:
        payload = stored.projection.to_dict()
        payload["is_stale"] = stale
        return self._clone(
            stored,
            projection=ProductionProjection.from_dict(payload),
            labeled_stale=stale,
        )

    def _clone(
        self,
        stored: StoredBudget,
        *,
        projection: ProductionProjection | None = None,
        lines: tuple[LedgerLine, ...] | None = None,
        actuals: tuple[ActualEntry, ...] | None = None,
        commitments: tuple[CommitmentEntry, ...] | None = None,
        total: Decimal | None = None,
        calibration: CalibrationReport | None = None,
        labeled_stale: bool | None = None,
        config_node_id: str | None = None,
        analysis_node_id: str | None = None,
    ) -> StoredBudget:
        return StoredBudget(
            projection=stored.projection if projection is None else projection,
            schedule_id=stored.schedule_id,
            currency=stored.currency,
            accounts=stored.accounts,
            lines=stored.lines if lines is None else lines,
            assumptions=stored.assumptions,
            actuals=stored.actuals if actuals is None else actuals,
            commitments=stored.commitments if commitments is None else commitments,
            total=stored.total if total is None else total,
            calibration=stored.calibration if calibration is None else calibration,
            labeled_stale=stored.labeled_stale if labeled_stale is None else labeled_stale,
            config_node_id=stored.config_node_id if config_node_id is None else config_node_id,
            analysis_node_id=(
                stored.analysis_node_id if analysis_node_id is None else analysis_node_id
            ),
        )

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
        self._require(principal, Action.VIEW_SENSITIVE_FINANCIAL, project_id, acl_epoch)

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
            object_kind="budget",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
