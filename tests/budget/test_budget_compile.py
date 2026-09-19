"""Schedule-first compile, formula totals, and reconciliation."""

from __future__ import annotations

from decimal import Decimal

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.budget.api import AmountEvidence, LineOrigin, round_money
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.schemas.api import BudgetMaturity, ProjectionKind


def test_schedule_precedes_budget_and_totals_reconcile(
    compiled_schedule, budget_stack
) -> None:
    stored = budget_stack.budget.compile(
        compiled_schedule.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
        maturity=BudgetMaturity.PRELIMINARY_PRODUCTION_ESTIMATE,
        incentive="1500.00",
    )
    assert stored.projection.kind is ProjectionKind.BUDGET_EVIDENCE
    assert stored.projection.budget_maturity is BudgetMaturity.PRELIMINARY_PRODUCTION_ESTIMATE
    assert stored.schedule_id == compiled_schedule.id
    summed = sum((line.amount for line in stored.lines), Decimal("0"))
    assert round_money(summed) == stored.total
    assert all(line.evidence.source for line in stored.lines)
    assert any(line.origin is LineOrigin.SCHEDULE for line in stored.lines)
    assert any(line.budget_class.value == "contingency" for line in stored.lines)
    assert any(line.budget_class.value == "incentive" for line in stored.lines)
    exported = budget_stack.budget.export_ledger(
        stored.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    assert format(stored.total, "f") in exported
    assert "not a validated accuracy claim" in exported.casefold()


def test_every_amount_is_formula_or_evidenced_estimate(
    compiled_schedule, budget_stack
) -> None:
    stored = budget_stack.budget.compile(
        compiled_schedule.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    for line in stored.lines:
        if line.origin in {LineOrigin.FORMULA, LineOrigin.SCHEDULE}:
            assert "*" in line.formula or "round" in line.formula
        else:
            assert line.evidence.as_of_date
            assert line.evidence.source
    shooting = next(line for line in stored.lines if line.account_code == "2100")
    expected = round_money(
        shooting.quantity * shooting.rate * (Decimal("1") + shooting.fringe_rate)
    )
    assert shooting.amount == expected


def test_viewer_cannot_read_financials(compiled_schedule, budget_stack) -> None:
    stored = budget_stack.budget.compile(
        compiled_schedule.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    actor = make_human_actor(
        organization_id=budget_stack.project.organization_id, display_name="Viewer"
    )
    budget_stack.identity.register_actor(actor)
    invitation = budget_stack.identity.invite(
        inviter_actor_id=budget_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=budget_stack.project.id,
        role=Role.VIEWER,
    )
    budget_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    viewer = budget_stack.identity.principal(actor.id)
    epoch = budget_stack.identity.acl_epoch()
    with pytest.raises(AuthorizationError):
        budget_stack.budget.get_budget(stored.id, principal=viewer, acl_epoch=epoch)


def test_override_requires_evidence(compiled_schedule, budget_stack) -> None:
    stored = budget_stack.budget.compile(
        compiled_schedule.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    target = stored.lines[0]
    updated = budget_stack.budget.override_line(
        stored.id,
        target.id,
        "999.99",
        AmountEvidence(
            source="vendor bid",
            as_of_date="2026-09-19",
            territory="US",
            currency="USD",
            note="bid packet page 2",
        ),
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    replaced = next(line for line in updated.lines if line.id == target.id)
    assert replaced.origin is LineOrigin.OVERRIDE
    assert replaced.amount == Decimal("999.99")
    assert replaced.evidence.source == "vendor bid"
    summed = sum((line.amount for line in updated.lines), Decimal("0"))
    assert round_money(summed) == updated.total
