"""Deterministic seeded boards, day/night packing, and explainable alternatives."""

from __future__ import annotations

from movie_muse.scheduling.api import DayPart


def _scene_boards(schedule) -> dict[str, int]:
    return {
        strip.scene.scene_id: board.index
        for board in schedule.boards
        for strip in board.strips
    }


def test_same_seed_is_deterministic(derived_breakdown, schedule_stack) -> None:
    first = schedule_stack.schedule.compile(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=7,
    )
    second = schedule_stack.schedule.compile(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=7,
        schedule_id=first.id,
    )
    assert _scene_boards(first) == _scene_boards(second)
    kitchen, alley, office = schedule_stack.scene_ids
    mapping = _scene_boards(first)
    assert mapping[kitchen] == mapping[office] or mapping[kitchen] != mapping[alley]
    exported = schedule_stack.schedule.export_boards(
        first.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
    )
    assert kitchen in exported
    assert "SEED 7" in exported


def test_day_scenes_do_not_follow_night_on_a_board(
    derived_breakdown, schedule_stack
) -> None:
    stored = schedule_stack.schedule.compile(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=3,
    )
    for board in stored.boards:
        parts = [strip.scene.day_part for strip in board.strips]
        if DayPart.NIGHT in parts and DayPart.DAY in parts:
            night_at = min(
                strip.order for strip in board.strips if strip.scene.day_part is DayPart.NIGHT
            )
            day_at = max(
                strip.order for strip in board.strips if strip.scene.day_part is DayPart.DAY
            )
            assert day_at < night_at


def test_alternatives_do_not_replace_canon(derived_breakdown, schedule_stack) -> None:
    stored = schedule_stack.schedule.compile(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=1,
    )
    scenario = schedule_stack.schedule.alternatives(
        stored.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=99,
    )
    assert scenario.seed == 99
    assert scenario.id != stored.id
    reloaded = schedule_stack.schedule.get_schedule(
        stored.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
    )
    assert reloaded.seed == 1
    assert _scene_boards(reloaded) == _scene_boards(stored)
