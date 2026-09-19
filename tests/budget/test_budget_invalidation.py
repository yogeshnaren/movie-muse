"""Stale schedules block current budget labeling and export."""

from __future__ import annotations

import pytest

from movie_muse.budget.api import ScheduleRequiredError, StaleBudgetError
from movie_muse.schemas.api import BudgetMaturity


def test_stale_schedule_cannot_compile_current_budget(
    compiled_schedule, budget_stack
) -> None:
    budget_stack.schedule.notify_breakdown_changed(
        compiled_schedule.breakdown_id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    with pytest.raises(ScheduleRequiredError):
        budget_stack.budget.compile(
            compiled_schedule.id,
            principal=budget_stack.principal,
            acl_epoch=budget_stack.epoch,
            maturity=BudgetMaturity.SCRIPT_BREAKDOWN_RANGE,
        )


def test_schedule_change_stales_existing_budget(
    compiled_schedule, budget_stack
) -> None:
    stored = budget_stack.budget.compile(
        compiled_schedule.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    stale_ids = budget_stack.budget.notify_schedule_changed(
        compiled_schedule.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    assert stored.id in stale_ids
    reloaded = budget_stack.budget.get_budget(
        stored.id,
        principal=budget_stack.principal,
        acl_epoch=budget_stack.epoch,
    )
    assert reloaded.labeled_stale is True
    assert reloaded.projection.is_stale is True
    with pytest.raises(StaleBudgetError):
        budget_stack.budget.export_ledger(
            stored.id,
            principal=budget_stack.principal,
            acl_epoch=budget_stack.epoch,
        )
