"""Chart of accounts, lines, evidence, calibration, and budget envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from movie_muse.budget.money import money_str, parse_money, round_money
from movie_muse.schemas.api import BudgetMaturity, ProductionProjection


class AccountClass(str, Enum):
    ABOVE_THE_LINE = "above_the_line"
    BELOW_THE_LINE = "below_the_line"
    POST = "post"
    OTHER = "other"


class BudgetClass(str, Enum):
    LABOR = "labor"
    LOCATION = "location"
    EQUIPMENT = "equipment"
    CONTINGENCY = "contingency"
    INCENTIVE = "incentive"
    FRINGE = "fringe"
    OTHER = "other"


class LineOrigin(str, Enum):
    FORMULA = "formula"
    ESTIMATE = "estimate"
    OVERRIDE = "override"
    SCHEDULE = "schedule"
    ACTUAL = "actual"
    COMMITMENT = "commitment"


@dataclass(frozen=True, slots=True)
class Account:
    code: str
    name: str
    account_class: AccountClass
    budget_class: BudgetClass
    department: str
    geography: str = "US"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "account_class": self.account_class.value,
            "budget_class": self.budget_class.value,
            "department": self.department,
            "geography": self.geography,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Account:
        return cls(
            code=str(data["code"]),
            name=str(data["name"]),
            account_class=AccountClass(str(data["account_class"])),
            budget_class=BudgetClass(str(data["budget_class"])),
            department=str(data["department"]),
            geography=str(data.get("geography", "US")),
        )


@dataclass(frozen=True, slots=True)
class AmountEvidence:
    source: str
    as_of_date: str
    territory: str
    currency: str
    note: str = ""
    rights_record_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "as_of_date": self.as_of_date,
            "territory": self.territory,
            "currency": self.currency,
            "note": self.note,
            "rights_record_id": self.rights_record_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AmountEvidence:
        return cls(
            source=str(data["source"]),
            as_of_date=str(data["as_of_date"]),
            territory=str(data["territory"]),
            currency=str(data["currency"]),
            note=str(data.get("note", "")),
            rights_record_id=(
                str(data["rights_record_id"]) if data.get("rights_record_id") else None
            ),
        )


@dataclass(frozen=True, slots=True)
class LedgerLine:
    id: str
    account_code: str
    origin: LineOrigin
    quantity: Decimal
    rate: Decimal
    unit: str
    fringe_rate: Decimal
    amount: Decimal
    currency: str
    evidence: AmountEvidence
    formula: str
    department: str
    geography: str
    budget_class: BudgetClass
    assumption_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "account_code": self.account_code,
            "origin": self.origin.value,
            "quantity": (
                money_str(self.quantity)
                if self.unit == "currency"
                else format(self.quantity, "f")
            ),
            "rate": money_str(self.rate),
            "unit": self.unit,
            "fringe_rate": format(self.fringe_rate, "f"),
            "amount": money_str(self.amount),
            "currency": self.currency,
            "evidence": self.evidence.to_dict(),
            "formula": self.formula,
            "department": self.department,
            "geography": self.geography,
            "budget_class": self.budget_class.value,
            "assumption_id": self.assumption_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LedgerLine:
        return cls(
            id=str(data["id"]),
            account_code=str(data["account_code"]),
            origin=LineOrigin(str(data["origin"])),
            quantity=parse_money(data["quantity"]),
            rate=round_money(data["rate"], currency=str(data["currency"])),
            unit=str(data["unit"]),
            fringe_rate=parse_money(data.get("fringe_rate", "0")),
            amount=round_money(data["amount"], currency=str(data["currency"])),
            currency=str(data["currency"]),
            evidence=AmountEvidence.from_dict(data["evidence"]),
            formula=str(data["formula"]),
            department=str(data["department"]),
            geography=str(data["geography"]),
            budget_class=BudgetClass(str(data["budget_class"])),
            assumption_id=str(data["assumption_id"]) if data.get("assumption_id") else None,
        )


@dataclass(frozen=True, slots=True)
class Assumption:
    id: str
    key: str
    value: str
    evidence: AmountEvidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "evidence": self.evidence.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Assumption:
        return cls(
            id=str(data["id"]),
            key=str(data["key"]),
            value=str(data["value"]),
            evidence=AmountEvidence.from_dict(data["evidence"]),
        )


@dataclass(frozen=True, slots=True)
class ActualEntry:
    id: str
    line_id: str
    amount: Decimal
    currency: str
    evidence: AmountEvidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "line_id": self.line_id,
            "amount": money_str(self.amount),
            "currency": self.currency,
            "evidence": self.evidence.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActualEntry:
        return cls(
            id=str(data["id"]),
            line_id=str(data["line_id"]),
            amount=round_money(data["amount"], currency=str(data["currency"])),
            currency=str(data["currency"]),
            evidence=AmountEvidence.from_dict(data["evidence"]),
        )


@dataclass(frozen=True, slots=True)
class CommitmentEntry:
    id: str
    line_id: str
    amount: Decimal
    currency: str
    evidence: AmountEvidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "line_id": self.line_id,
            "amount": money_str(self.amount),
            "currency": self.currency,
            "evidence": self.evidence.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommitmentEntry:
        return cls(
            id=str(data["id"]),
            line_id=str(data["line_id"]),
            amount=round_money(data["amount"], currency=str(data["currency"])),
            currency=str(data["currency"]),
            evidence=AmountEvidence.from_dict(data["evidence"]),
        )


@dataclass(frozen=True, slots=True)
class CalibrationSlice:
    dimension: str
    key: str
    coverage: float
    abs_error: float
    bias: float
    line_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "key": self.key,
            "coverage": self.coverage,
            "abs_error": self.abs_error,
            "bias": self.bias,
            "line_count": self.line_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationSlice:
        return cls(
            dimension=str(data["dimension"]),
            key=str(data["key"]),
            coverage=float(data["coverage"]),
            abs_error=float(data["abs_error"]),
            bias=float(data["bias"]),
            line_count=int(data["line_count"]),
        )


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    maturity: BudgetMaturity
    validated: bool
    slices: tuple[CalibrationSlice, ...]
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "maturity": self.maturity.value,
            "validated": self.validated,
            "slices": [item.to_dict() for item in self.slices],
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationReport:
        return cls(
            maturity=BudgetMaturity(str(data["maturity"])),
            validated=bool(data["validated"]),
            slices=tuple(CalibrationSlice.from_dict(item) for item in data.get("slices", ())),
            disclaimer=str(data["disclaimer"]),
        )


@dataclass(frozen=True, slots=True)
class BudgetScenario:
    id: str
    label: str
    seed: int
    rate_delta: Decimal
    total: Decimal
    currency: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "seed": self.seed,
            "rate_delta": format(self.rate_delta, "f"),
            "total": money_str(self.total),
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BudgetScenario:
        return cls(
            id=str(data["id"]),
            label=str(data["label"]),
            seed=int(data["seed"]),
            rate_delta=parse_money(data["rate_delta"]),
            total=round_money(data["total"], currency=str(data["currency"])),
            currency=str(data["currency"]),
        )


@dataclass(frozen=True, slots=True)
class StoredBudget:
    projection: ProductionProjection
    schedule_id: str
    currency: str
    accounts: tuple[Account, ...]
    lines: tuple[LedgerLine, ...]
    assumptions: tuple[Assumption, ...]
    actuals: tuple[ActualEntry, ...]
    commitments: tuple[CommitmentEntry, ...]
    total: Decimal
    calibration: CalibrationReport
    labeled_stale: bool = False
    config_node_id: str | None = None
    analysis_node_id: str | None = None

    @property
    def id(self) -> str:
        return self.projection.id

    @property
    def project_id(self) -> str:
        return self.projection.project_id

    @property
    def maturity(self) -> BudgetMaturity:
        if self.projection.budget_maturity is None:
            raise ValueError("budget projection missing maturity")
        return self.projection.budget_maturity

    def to_dict(self) -> dict[str, Any]:
        return {
            "projection": self.projection.to_dict(),
            "schedule_id": self.schedule_id,
            "currency": self.currency,
            "accounts": [item.to_dict() for item in self.accounts],
            "lines": [item.to_dict() for item in self.lines],
            "assumptions": [item.to_dict() for item in self.assumptions],
            "actuals": [item.to_dict() for item in self.actuals],
            "commitments": [item.to_dict() for item in self.commitments],
            "total": money_str(self.total),
            "calibration": self.calibration.to_dict(),
            "labeled_stale": self.labeled_stale,
            "config_node_id": self.config_node_id,
            "analysis_node_id": self.analysis_node_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoredBudget:
        currency = str(data["currency"])
        return cls(
            projection=ProductionProjection.from_dict(data["projection"]),
            schedule_id=str(data["schedule_id"]),
            currency=currency,
            accounts=tuple(Account.from_dict(item) for item in data.get("accounts", ())),
            lines=tuple(LedgerLine.from_dict(item) for item in data.get("lines", ())),
            assumptions=tuple(Assumption.from_dict(item) for item in data.get("assumptions", ())),
            actuals=tuple(ActualEntry.from_dict(item) for item in data.get("actuals", ())),
            commitments=tuple(
                CommitmentEntry.from_dict(item) for item in data.get("commitments", ())
            ),
            total=round_money(data["total"], currency=currency),
            calibration=CalibrationReport.from_dict(data["calibration"]),
            labeled_stale=bool(data.get("labeled_stale", False)),
            config_node_id=str(data["config_node_id"]) if data.get("config_node_id") else None,
            analysis_node_id=(
                str(data["analysis_node_id"]) if data.get("analysis_node_id") else None
            ),
        )
