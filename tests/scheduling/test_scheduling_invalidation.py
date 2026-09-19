"""Breakdown changes stale schedules; pins survive recompile; export is fail-closed."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.scheduling.api import StaleScheduleError


def _board_for(schedule, scene_id: str) -> int | None:
    for board in schedule.boards:
        if any(strip.scene.scene_id == scene_id for strip in board.strips):
            return board.index
    return None


def test_breakdown_change_invalidates_schedule(
    derived_breakdown, schedule_stack
) -> None:
    stored = schedule_stack.schedule.compile(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=1,
    )
    assert stored.labeled_stale is False
    stale_ids = schedule_stack.schedule.notify_breakdown_changed(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
    )
    assert stored.id in stale_ids
    reloaded = schedule_stack.schedule.get_schedule(
        stored.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
    )
    assert reloaded.labeled_stale is True
    assert reloaded.projection.is_stale is True
    with pytest.raises(StaleScheduleError):
        schedule_stack.schedule.export_boards(
            stored.id,
            principal=schedule_stack.principal,
            acl_epoch=schedule_stack.epoch,
        )


def test_pin_survives_recompile(derived_breakdown, schedule_stack) -> None:
    stored = schedule_stack.schedule.compile(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=1,
    )
    alley = schedule_stack.scene_ids[1]
    pinned = schedule_stack.schedule.pin(
        stored.id,
        alley,
        3,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
    )
    assert _board_for(pinned, alley) == 3
    rebuilt = schedule_stack.schedule.compile(
        derived_breakdown.projection.id,
        principal=schedule_stack.principal,
        acl_epoch=schedule_stack.epoch,
        seed=11,
        schedule_id=pinned.id,
    )
    assert _board_for(rebuilt, alley) == 3
    assert any(item.scene_id == alley and item.board_index == 3 for item in rebuilt.pins)


def test_viewer_cannot_compile(derived_breakdown, schedule_stack) -> None:
    actor = make_human_actor(
        organization_id=schedule_stack.project.organization_id, display_name="Viewer"
    )
    schedule_stack.identity.register_actor(actor)
    invitation = schedule_stack.identity.invite(
        inviter_actor_id=schedule_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=schedule_stack.project.id,
        role=Role.VIEWER,
    )
    schedule_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    viewer = schedule_stack.identity.principal(actor.id)
    epoch = schedule_stack.identity.acl_epoch()
    with pytest.raises(AuthorizationError):
        schedule_stack.schedule.compile(
            derived_breakdown.projection.id,
            principal=viewer,
            acl_epoch=epoch,
            seed=1,
        )
