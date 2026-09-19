"""Hard constraints fail closed and remain explainable."""

from __future__ import annotations

import pytest

from movie_muse.scheduling.api import InfeasibleScheduleError, ResourceKind


def _board_for(schedule, scene_id: str) -> int | None:
    for board in schedule.boards:
        if any(strip.scene.scene_id == scene_id for strip in board.strips):
            return board.index
    return None


def test_stunt_and_minor_never_share_a_board(derived_breakdown, schedule_stack) -> None:
    stored = schedule_stack.schedule.compile(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=2,
    )
    kitchen, alley, _office = schedule_stack.scene_ids
    assert _board_for(stored, kitchen) is not None
    assert _board_for(stored, alley) is not None
    assert _board_for(stored, kitchen) != _board_for(stored, alley)
    explanations = " ".join(item.explanation for item in stored.infeasible + stored.conflicts)
    assert "stunt" not in explanations or stored.infeasible == ()


def test_cast_unavailability_is_not_silently_broken(
    derived_breakdown, schedule_stack
) -> None:
    stored = schedule_stack.schedule.compile(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=4,
    )
    blocked = schedule_stack.schedule.block_resource(
        stored.id,
        ResourceKind.CAST,
        "ADA",
        1,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
    )
    for board in blocked.boards:
        if board.index != 1:
            continue
        for strip in board.strips:
            assert "ada" not in strip.scene.cast
    codes = {item.code for item in blocked.infeasible}
    assert not codes or codes <= {
        "cast_unavailable",
        "no_feasible_board",
        "labor_rest",
        "day_capacity",
        "safety_stunt_minor",
        "day_after_night",
        "location_unavailable",
    }


def test_manual_move_refuses_hard_safety_break(
    derived_breakdown, schedule_stack
) -> None:
    stored = schedule_stack.schedule.compile(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=5,
    )
    kitchen, alley, _office = schedule_stack.scene_ids
    kitchen_board = _board_for(stored, kitchen)
    assert kitchen_board is not None
    with pytest.raises(InfeasibleScheduleError) as raised:
        schedule_stack.schedule.move_scene(
            stored.id,
            alley,
            kitchen_board,
            principal=schedule_stack.principal,
            acl_epoch=schedule_stack.epoch,
        )
    assert raised.value.explanations
    assert any("safety" in item or "stunt" in item or "minor" in item for item in raised.value.explanations)
    unchanged = schedule_stack.schedule.get_schedule(
        stored.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
    )
    assert _board_for(unchanged, alley) != kitchen_board


def test_explain_lists_conflicts(derived_breakdown, schedule_stack) -> None:
    stored = schedule_stack.schedule.compile(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=8,
    )
    schedule_stack.schedule.set_scene_duration(
        stored.id,
        schedule_stack.scene_ids[0],
        700,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
    )
    stretched = schedule_stack.schedule.set_scene_duration(
        stored.id,
        schedule_stack.scene_ids[2],
        700,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
    )
    kitchen_board = _board_for(stretched, schedule_stack.scene_ids[0])
    office_board = _board_for(stretched, schedule_stack.scene_ids[2])
    assert kitchen_board != office_board
    explained = schedule_stack.schedule.explain(
        stretched.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
    )
    assert all(item.explanation for item in explained)
